from app.ingest import ingest_corpus
from app.retrieval import RetrievedChunk, retrieve, rrf_fuse


def rc(i: int, sim: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(id=i, source_file="f.md", heading="", chunk_index=0, text="", similarity=sim)


def test_rrf_rewards_agreement_between_lists():
    # Chunk 2 is 2nd in both lists; chunk 1 is 1st in one list only.
    fused = rrf_fuse({"vector": [rc(1), rc(2)], "keyword": [rc(3), rc(2)]}, k=3)
    assert fused[0].id == 2
    assert fused[0].ranks == {"vector": 2, "keyword": 2}
    assert abs(fused[0].score - 2 / 62) < 1e-12


def test_rrf_respects_k_and_is_deterministic():
    lists = {"vector": [rc(1), rc(2), rc(3)], "keyword": [rc(4), rc(5)]}
    first = [c.id for c in rrf_fuse(lists, k=2)]
    assert len(first) == 2
    assert first == [c.id for c in rrf_fuse(lists, k=2)]


def test_vector_search_finds_right_file(conn, embedder, corpus_dir):
    ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    hits = retrieve(conn, embedder, "rainfall charts matplotlib", "s300_o50", k=1, mode="vector")
    assert hits[0].source_file == "beta.md"
    assert 0 < hits[0].similarity <= 1


def test_keyword_search_matches_any_term_not_all(conn, embedder, corpus_dir):
    ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    # "unicorn" appears nowhere; with AND semantics this would return nothing.
    hits = retrieve(conn, embedder, "unicorn rainfall", "s300_o50", k=5, mode="keyword")
    assert [h.source_file for h in hits] == ["beta.md"]


def test_keyword_search_with_no_match_is_empty(conn, embedder, corpus_dir):
    ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    assert retrieve(conn, embedder, "zebra croissant", "s300_o50", k=5, mode="keyword") == []


def test_hybrid_results_carry_similarity_and_ranks(conn, embedder, corpus_dir):
    ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    hits = retrieve(conn, embedder, "alpha redis storage", "s300_o50", k=2, mode="hybrid")
    assert hits and len(hits) <= 2
    assert hits[0].source_file == "alpha.md"
    assert set(hits[0].ranks) <= {"vector", "keyword"} and hits[0].ranks


def test_search_stays_inside_its_collection(conn, embedder, corpus_dir):
    ingest_corpus(conn, embedder, corpus_dir, 300, 50)
    ingest_corpus(conn, embedder, corpus_dir, 20, 5)
    for mode in ("vector", "keyword", "hybrid"):
        hits = retrieve(conn, embedder, "alpha port", "s20_o5", k=10, mode=mode)
        ids = [h.id for h in hits]
        rows = conn.execute("SELECT DISTINCT collection FROM chunks WHERE id = ANY(%s)", (ids,)).fetchall()
        assert rows == [("s20_o5",)], mode
