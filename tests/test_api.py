"""HTTP API end to end, with a fake embedder and fake LLM (no network)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import FakeEmbedder, FakeLLM, cite_first


@pytest.fixture
def client(conn, corpus_dir, test_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", test_db_url)
    monkeypatch.setenv("CORPUS_DIR", str(corpus_dir))
    monkeypatch.setenv("CHUNK_SIZE", "300")
    monkeypatch.setenv("CHUNK_OVERLAP", "50")
    monkeypatch.setenv("MIN_SIMILARITY", "0.05")
    # Make sure nothing real can be built if a test leaves llm unset.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("OLLAMA_URL", "")
    app.state.embedder = FakeEmbedder()
    app.state.llm = FakeLLM()
    with TestClient(app) as c:
        yield c
    app.state.embedder = None
    app.state.llm = None


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ingest_is_idempotent_over_http(client):
    first = client.post("/ingest", json={}).json()
    assert first["collection"] == "s300_o50" and first["inserted"] > 0
    second = client.post("/ingest", json={}).json()
    assert second["inserted"] == 0 and second["skipped"] == first["chunks"]


def test_ingest_rejects_bad_overlap(client):
    assert client.post("/ingest", json={"chunk_size": 100, "overlap": 100}).status_code == 422


def test_ingest_empty_corpus_is_400(client, tmp_path, monkeypatch):
    empty = tmp_path / "nothing"
    empty.mkdir()
    monkeypatch.setenv("CORPUS_DIR", str(empty))
    r = client.post("/ingest", json={})
    assert r.status_code == 400 and "no documents" in r.json()["detail"]


def test_search(client):
    client.post("/ingest", json={})
    r = client.post("/search", json={"question": "rainfall charts", "k": 1, "mode": "hybrid"})
    assert r.status_code == 200
    hit = r.json()["results"][0]
    assert hit["source_file"] == "beta.md" and hit["chunk_id"] > 0


def test_ask_returns_cited_answer(client):
    client.post("/ingest", json={})
    app.state.llm = FakeLLM(cite_first())
    r = client.post("/ask", json={"question": "default port of alpha", "k": 3, "mode": "vector"})
    body = r.json()
    assert r.status_code == 200
    assert set(body) == {"answer", "sources", "abstained", "latency_ms", "reason", "top_similarity"}
    assert body["abstained"] is False
    assert body["sources"][0]["source_file"] == "alpha.md"
    assert isinstance(body["latency_ms"], int)


def test_ask_abstains_on_unrelated_question(client):
    client.post("/ingest", json={})
    r = client.post("/ask", json={"question": "zebra croissant quantum"}).json()
    assert r["abstained"] is True and r["reason"] == "low_similarity" and r["sources"] == []


def test_ask_validates_input(client):
    assert client.post("/ask", json={"question": ""}).status_code == 422
    assert client.post("/ask", json={"question": "x", "mode": "bogus"}).status_code == 422
    assert client.post("/ask", json={"question": "x", "k": 0}).status_code == 422


def test_ask_without_llm_is_503(client):
    app.state.llm = None
    app.state.llm_error = "no LLM configured: set GEMINI_API_KEY or OLLAMA_URL"
    r = client.post("/ask", json={"question": "default port of alpha"})
    assert r.status_code == 503
