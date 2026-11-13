"""Idempotent ingestion: chunk -> hash -> embed only new chunks -> insert.

Re-running on unchanged files inserts 0 rows and embeds nothing.
If a file changed, its new chunks are inserted and its chunks that no longer
exist are deleted, so the index never serves stale text.

CLI:
    python -m app.ingest --size 300 --overlap 50
"""

from __future__ import annotations

import argparse
import hashlib
import time
from dataclasses import asdict, dataclass

import psycopg

from app.chunker import Chunk, chunk_corpus
from app.config import collection_name, get_settings
from app.embeddings import Embedder
from app.loader import load_corpus


@dataclass
class IngestReport:
    collection: str
    files: int
    chunks: int
    inserted: int
    skipped: int
    deleted: int
    duration_ms: int


def content_hash(collection: str, chunk: Chunk) -> str:
    # \x00 separators: ("ab", "c") and ("a", "bc") must not hash the same.
    key = "\x00".join([collection, chunk.source_file, chunk.heading, chunk.text])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def embedding_input(chunk: Chunk) -> str:
    """What gets embedded: heading path + text, so a chunk 'knows' which
    project and section it belongs to even if the text never says it."""
    return f"{chunk.heading}\n\n{chunk.text}" if chunk.heading else chunk.text


def ingest_chunks(
    conn: psycopg.Connection,
    embedder: Embedder,
    chunks: list[Chunk],
    collection: str,
    source_files: list[str],
    full_sync: bool = False,
) -> IngestReport:
    """Insert new chunks and delete stale ones.

    full_sync=False: only `source_files` are synced (their stale chunks go).
    full_sync=True:  `chunks` is the whole collection; anything else in the
                     collection is deleted, including files that were removed.
    """
    start = time.perf_counter()

    # De-duplicate within this batch too (same hash twice -> keep the first).
    by_hash: dict[str, Chunk] = {}
    for c in chunks:
        by_hash.setdefault(content_hash(collection, c), c)
    hashes = list(by_hash)

    existing = {
        row[0]
        for row in conn.execute(
            "SELECT content_hash FROM chunks WHERE content_hash = ANY(%s)", (hashes,)
        )
    }
    new = [h for h in hashes if h not in existing]

    # Only embed what we will actually insert: embedding is the slow part.
    vectors = embedder.embed([embedding_input(by_hash[h]) for h in new])

    inserted = 0
    with conn.transaction():
        with conn.cursor() as cur:
            for h, vec in zip(new, vectors):
                c = by_hash[h]
                cur.execute(
                    """
                    INSERT INTO chunks
                        (collection, source_file, heading, chunk_index, text, content_hash, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (content_hash) DO NOTHING
                    """,
                    (collection, c.source_file, c.heading, c.chunk_index, c.text, h, vec),
                )
                inserted += cur.rowcount  # 0 if a concurrent ingest won the race

            # Remove chunks this ingest no longer produces: a README changed,
            # or (full sync) a file was removed from the corpus. Other
            # collections are never touched.
            if full_sync:
                cur.execute(
                    "DELETE FROM chunks WHERE collection = %s AND NOT (content_hash = ANY(%s))",
                    (collection, hashes),
                )
            else:
                cur.execute(
                    """
                    DELETE FROM chunks
                    WHERE collection = %s
                      AND source_file = ANY(%s)
                      AND NOT (content_hash = ANY(%s))
                    """,
                    (collection, source_files, hashes),
                )
            deleted = cur.rowcount

    return IngestReport(
        collection=collection,
        files=len(source_files),
        chunks=len(hashes),
        inserted=inserted,
        skipped=len(hashes) - inserted,
        deleted=deleted,
        duration_ms=round((time.perf_counter() - start) * 1000),
    )


def ingest_corpus(
    conn: psycopg.Connection,
    embedder: Embedder,
    corpus_dir,
    chunk_size: int,
    overlap: int,
) -> IngestReport:
    """Sync one collection with the corpus folder (full sync: a README removed
    from the folder is removed from the index too)."""
    docs = load_corpus(corpus_dir)
    if not docs:
        # A full sync with zero documents would delete the whole collection.
        # An empty corpus is almost always a wrong path, so refuse instead.
        raise ValueError(f"no documents found in corpus folder {corpus_dir!s}")
    chunks = chunk_corpus(docs, chunk_size, overlap)
    return ingest_chunks(
        conn,
        embedder,
        chunks,
        collection=collection_name(chunk_size, overlap),
        source_files=[d.source_file for d in docs],
        full_sync=True,
    )


def _main() -> None:
    from app.db import apply_schema, connect
    from app.embeddings import SentenceTransformerEmbedder

    s = get_settings()
    parser = argparse.ArgumentParser(description="Ingest the corpus into Postgres.")
    parser.add_argument("--size", type=int, default=s.chunk_size)
    parser.add_argument("--overlap", type=int, default=s.chunk_overlap)
    args = parser.parse_args()

    embedder = SentenceTransformerEmbedder(s.embedding_model)
    with connect(s.database_url) as conn:
        apply_schema(conn)
        report = ingest_corpus(conn, embedder, s.corpus_dir, args.size, args.overlap)
    print(asdict(report))


if __name__ == "__main__":
    _main()
