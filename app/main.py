"""FastAPI app.

Run:  uvicorn app.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel, Field

from app.config import collection_name, get_settings
from app.db import apply_schema, connect
from app.embeddings import Embedder
from app.ingest import ingest_corpus
from app.retrieval import Mode, retrieve


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Load the model once at startup (~2-5 s), not on every request.
    # Tests set app.state.embedder to a fake before starting, so skip then.
    if getattr(app.state, "embedder", None) is None:
        from app.embeddings import SentenceTransformerEmbedder

        app.state.embedder = SentenceTransformerEmbedder(settings.embedding_model)
    with connect(settings.database_url) as conn:
        apply_schema(conn)
    yield


app = FastAPI(title="Pramaan", version="0.1.0", lifespan=lifespan)


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder


def get_conn():
    conn = connect(get_settings().database_url)
    try:
        yield conn
    finally:
        conn.close()


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
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="overlap must be smaller than chunk_size")
    report = ingest_corpus(conn, embedder, s.corpus_dir, size, overlap)
    return IngestResponse(**asdict(report))
