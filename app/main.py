"""FastAPI app.

Run:  uvicorn app.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db import apply_schema, connect
from app.embeddings import Embedder
from app.ingest import ingest_corpus


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
