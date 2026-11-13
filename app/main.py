"""FastAPI app.

Run:  uvicorn app.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import collection_name, get_settings
from app.db import apply_schema, connect
from app.embeddings import Embedder
from app.ingest import ingest_corpus
from app.answer import answer_question
from app.llm import LLMError, build_llm
from app.retrieval import Mode, retrieve


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Load the model once at startup (~2-5 s), not on every request.
    # Tests set app.state.embedder to a fake before starting, so skip then.
    if getattr(app.state, "embedder", None) is None:
        from app.embeddings import SentenceTransformerEmbedder

        app.state.embedder = SentenceTransformerEmbedder(settings.embedding_model)
    if getattr(app.state, "llm", None) is None:
        try:
            app.state.llm = build_llm(settings)
        except LLMError as exc:  # server still starts; /ask will return 503
            app.state.llm = None
            app.state.llm_error = str(exc)
    with connect(settings.database_url) as conn:
        apply_schema(conn)
    yield


app = FastAPI(title="Pramaan", version="0.1.0", lifespan=lifespan)


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder


def get_conn():
    # `with` commits when the request succeeds and rolls back if it raises.
    # A bare conn.close() would silently roll back every write: POST /ingest
    # reported "inserted" but stored nothing on a fresh database (caught by
    # tests/test_api.py).
    with connect(get_settings().database_url) as conn:
        yield conn


class IngestRequest(BaseModel):
    # Only chunking parameters are accepted. The corpus folder is fixed by the
    # server's config: an API that reads any path it is given is a security hole.
    chunk_size: int | None = Field(default=None, ge=20, le=4000)
    overlap: int | None = Field(default=None, ge=0)


class IngestResponse(BaseModel):
    collection: str
    files: int
    chunks: int
    inserted: int
    skipped: int
    deleted: int
    duration_ms: int


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    k: int = Field(default=5, ge=1, le=50)
    mode: Mode = "vector"
    collection: str | None = None  # default: from CHUNK_SIZE / CHUNK_OVERLAP


class SearchHit(BaseModel):
    chunk_id: int
    source_file: str
    heading: str
    similarity: float
    score: float
    ranks: dict[str, int]
    text: str


class SearchResponse(BaseModel):
    collection: str
    mode: Mode
    results: list[SearchHit]


def default_collection() -> str:
    s = get_settings()
    return collection_name(s.chunk_size, s.chunk_overlap)


@app.post("/search", response_model=SearchResponse)
def search(
    req: SearchRequest,
    embedder: Embedder = Depends(get_embedder),
    conn=Depends(get_conn),
) -> SearchResponse:
    """Retrieval only, no LLM. Useful for debugging what /ask will see."""
    collection = req.collection or default_collection()
    hits = retrieve(conn, embedder, req.question, collection, req.k, req.mode)
    return SearchResponse(
        collection=collection,
        mode=req.mode,
        results=[
            SearchHit(
                chunk_id=h.id, source_file=h.source_file, heading=h.heading,
                similarity=round(h.similarity, 4), score=round(h.score, 6),
                ranks=h.ranks, text=h.text,
            )
            for h in hits
        ],
    )


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)
    mode: Mode = "vector"
    collection: str | None = None


class SourceOut(BaseModel):
    source_file: str
    heading: str
    chunk_id: int


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    abstained: bool
    latency_ms: int
    reason: str | None = None  # why it abstained (null when answered)
    top_similarity: float


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, request: Request, embedder: Embedder = Depends(get_embedder), conn=Depends(get_conn)):
    llm = request.app.state.llm
    if llm is None:
        raise HTTPException(status_code=503, detail=getattr(request.app.state, "llm_error", "no LLM configured"))
    s = get_settings()
    result = answer_question(
        conn, embedder, llm, req.question,
        collection=req.collection or default_collection(),
        k=req.k, mode=req.mode, min_similarity=s.min_similarity,
    )
    return AskResponse(
        answer=result.answer,
        sources=[SourceOut(**src.__dict__) for src in result.sources],
        abstained=result.abstained,
        latency_ms=result.latency_ms,
        reason=result.reason,
        top_similarity=round(result.top_similarity, 4),
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
def ingest(
    req: IngestRequest | None = None,
    embedder: Embedder = Depends(get_embedder),
    conn=Depends(get_conn),
) -> IngestResponse:
    s = get_settings()
    req = req or IngestRequest()
    size = req.chunk_size or s.chunk_size
    overlap = s.chunk_overlap if req.overlap is None else req.overlap
    if overlap >= size:
        raise HTTPException(status_code=422, detail="overlap must be smaller than chunk_size")
    try:
        report = ingest_corpus(conn, embedder, s.corpus_dir, size, overlap)
    except ValueError as exc:  # e.g. empty corpus folder: refuse rather than wipe the index
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IngestResponse(**asdict(report))
