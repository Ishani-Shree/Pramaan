"""Retrieval: vector search, keyword (full-text) search, and hybrid (RRF).

CLI:
    python -m app.retrieval "How does ReachInbox use BullMQ?" --mode hybrid
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import psycopg

Mode = Literal["vector", "hybrid", "keyword"]

RRF_K = 60  # standard constant from the original RRF paper (Cormack et al., 2009)
CANDIDATES = 20  # how many results each method contributes to the fusion


@dataclass
class RetrievedChunk:
    id: int
    source_file: str
    heading: str
    chunk_index: int
    text: str
    similarity: float  # cosine similarity to the question, always filled in
    score: float = 0.0  # ranking score of the mode used (cosine, ts_rank or RRF)
    ranks: dict[str, int] = field(default_factory=dict)  # e.g. {"vector": 1, "keyword": 4}


_COLUMNS = "id, source_file, heading, chunk_index, text, 1 - (embedding <=> %(q)s) AS similarity"


def _rows(cur) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(id=r[0], source_file=r[1], heading=r[2], chunk_index=r[3], text=r[4], similarity=float(r[5]))
        for r in cur.fetchall()
    ]


def vector_search(conn: psycopg.Connection, query_vec: np.ndarray, collection: str, k: int) -> list[RetrievedChunk]:
    """Top-k chunks by cosine similarity. `<=>` is pgvector's cosine *distance*
    (1 - similarity); ORDER BY distance lets Postgres use the HNSW index."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {_COLUMNS}
            FROM chunks
            WHERE collection = %(c)s
            ORDER BY embedding <=> %(q)s
            LIMIT %(k)s
            """,
            {"q": query_vec, "c": collection, "k": k},
        )
        results = _rows(cur)
    for rank, r in enumerate(results, start=1):
        r.score, r.ranks["vector"] = r.similarity, rank
    return results


def keyword_search(
    conn: psycopg.Connection, question: str, query_vec: np.ndarray, collection: str, k: int
) -> list[RetrievedChunk]:
    """Top-k chunks by full-text rank.

    plainto_tsquery stems the words and drops stop words ("how", "does", "the"),
    but it ANDs the remaining terms: a chunk must contain *every* word. For a
    natural-language question that is far too strict, so the ANDs are turned
    into ORs and ts_rank_cd rewards chunks that match more terms, closer together.
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH q AS (
                SELECT to_tsquery('english',
                         replace(plainto_tsquery('english', %(text)s)::text, '&', '|')) AS tsq
            )
            SELECT {_COLUMNS}, ts_rank_cd(tsv, q.tsq) AS rank
            FROM chunks, q
            WHERE collection = %(c)s AND tsv @@ q.tsq
            ORDER BY rank DESC, id
            LIMIT %(k)s
            """,
            {"text": question, "q": query_vec, "c": collection, "k": k},
        )
        rows = cur.fetchall()
    results = []
    for rank, r in enumerate(rows, start=1):
        chunk = RetrievedChunk(
            id=r[0], source_file=r[1], heading=r[2], chunk_index=r[3], text=r[4],
            similarity=float(r[5]), score=float(r[6]),
        )
        chunk.ranks["keyword"] = rank
        results.append(chunk)
    return results


def rrf_fuse(result_lists: dict[str, list[RetrievedChunk]], k: int, rrf_k: int = RRF_K) -> list[RetrievedChunk]:
    """Reciprocal rank fusion: score(chunk) = sum over lists of 1 / (rrf_k + rank).

    Only ranks are used, never the raw scores, because cosine similarity
    (0..1) and ts_rank (unbounded) are on different scales and can't be added.
    """
    fused: dict[int, RetrievedChunk] = {}
    for name, results in result_lists.items():
        for rank, r in enumerate(results, start=1):
            chunk = fused.setdefault(r.id, RetrievedChunk(**{**r.__dict__, "score": 0.0, "ranks": {}}))
            chunk.score += 1.0 / (rrf_k + rank)
            chunk.ranks[name] = rank
    # Ties (same fused score) broken by cosine similarity, then id: deterministic.
    ordered = sorted(fused.values(), key=lambda c: (-c.score, -c.similarity, c.id))
    return ordered[:k]


def retrieve(
    conn: psycopg.Connection,
    embedder,
    question: str,
    collection: str,
    k: int = 5,
    mode: Mode = "vector",
) -> list[RetrievedChunk]:
    query_vec = embedder.embed([question])[0]
    if mode == "vector":
        return vector_search(conn, query_vec, collection, k)
    if mode == "keyword":
        return keyword_search(conn, question, query_vec, collection, k)
    if mode == "hybrid":
        n = max(CANDIDATES, k)
        return rrf_fuse(
            {
                "vector": vector_search(conn, query_vec, collection, n),
                "keyword": keyword_search(conn, question, query_vec, collection, n),
            },
            k,
        )
    raise ValueError(f"unknown mode {mode!r}")


def _main() -> None:
    from app.config import collection_name, get_settings
    from app.db import connect
    from app.embeddings import SentenceTransformerEmbedder

    s = get_settings()
    parser = argparse.ArgumentParser(description="Search the index.")
    parser.add_argument("question")
    parser.add_argument("--mode", choices=["vector", "keyword", "hybrid", "all"], default="all")
    parser.add_argument("-k", type=int, default=s.top_k)
    parser.add_argument("--size", type=int, default=s.chunk_size)
    parser.add_argument("--overlap", type=int, default=s.chunk_overlap)
    args = parser.parse_args()

    embedder = SentenceTransformerEmbedder(s.embedding_model)
    collection = collection_name(args.size, args.overlap)
    modes = ["vector", "keyword", "hybrid"] if args.mode == "all" else [args.mode]
    with connect(s.database_url) as conn:
        for mode in modes:
            print(f"\n[{mode}]  collection={collection}  q={args.question!r}")
            for i, r in enumerate(retrieve(conn, embedder, args.question, collection, args.k, mode), 1):
                ranks = " ".join(f"{n[0]}{v}" for n, v in r.ranks.items())
                print(f" {i}. sim={r.similarity:.3f} score={r.score:.4f} [{ranks:<7}] "
                      f"#{r.id} {r.source_file} :: {r.heading[:60]}")


if __name__ == "__main__":
    _main()
