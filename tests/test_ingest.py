import pytest

from app.chunker import Chunk
from app.ingest import content_hash, ingest_corpus


def count(conn, collection=None) -> int:
    if collection:
        return conn.execute("SELECT count(*) FROM chunks WHERE collection = %s", (collection,)).fetchone()[0]
    return conn.execute("SELECT count(*) FROM chunks").fetchone()[0]


def test_second_ingest_inserts_nothing_and_embeds_nothing(conn, embedder, corpus_dir):
    first = ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    assert first.inserted == first.chunks > 0
    assert first.skipped == 0

    calls_before = len(embedder.calls)
    second = ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    assert (second.inserted, second.skipped, second.deleted) == (0, first.chunks, 0)
    # Nothing new -> the (slow) embedder was given nothing to embed.
    assert all(len(batch) == 0 for batch in embedder.calls[calls_before:])
    assert count(conn) == first.chunks


def test_changed_file_replaces_only_its_stale_chunk(conn, embedder, corpus_dir):
    first = ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    alpha = corpus_dir / "alpha.md"
    alpha.write_text(alpha.read_text() + "\nAlpha also supports retries.\n")

    report = ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    assert report.inserted == 1 and report.deleted == 1
    assert count(conn) == first.chunks
    texts = [r[0] for r in conn.execute("SELECT text FROM chunks WHERE source_file = 'alpha.md'")]
    assert any("retries" in t for t in texts)


def test_removed_file_is_removed_from_index(conn, embedder, corpus_dir):
    ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    (corpus_dir / "beta.md").unlink()

    report = ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    assert report.deleted >= 1
    files = {r[0] for r in conn.execute("SELECT DISTINCT source_file FROM chunks")}
    assert files == {"alpha.md"}


def test_empty_corpus_is_refused_not_wiped(conn, embedder, corpus_dir, tmp_path):
    ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    before = count(conn)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no documents"):
        ingest_corpus(conn, embedder, empty, 300, 50)
    assert count(conn) == before


def test_collections_are_independent(conn, embedder, corpus_dir):
    a = ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    b = ingest_corpus(conn, embedder, corpus_dir, 20, 5)
    assert count(conn, "s300_o50") == a.chunks
    assert count(conn, "s20_o5") == b.chunks
    # Same text in both configs must not collide on the UNIQUE hash.
    assert b.inserted == b.chunks
    again = ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    assert again.inserted == 0 and again.deleted == 0
    assert count(conn, "s20_o5") == b.chunks


def test_hash_fields_cannot_run_together():
    a = Chunk("ab", "c", 0, "text")
    b = Chunk("a", "bc", 0, "text")
    assert content_hash("s300_o50", a) != content_hash("s300_o50", b)
    assert content_hash("s300_o50", a) != content_hash("s800_o50", a)
