"""Settings read from environment variables (and .env if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_url: str
    embedding_model: str
    corpus_dir: Path
    chunk_size: int
    chunk_overlap: int
    top_k: int
    min_similarity: float
    gemini_api_key: str
    gemini_model: str
    ollama_url: str
    ollama_model: str


def get_settings() -> Settings:
    env = os.getenv
    return Settings(
        database_url=env("DATABASE_URL", "postgresql://pramaan:pramaan@localhost:5434/pramaan"),
        embedding_model=env("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        corpus_dir=Path(env("CORPUS_DIR", str(PROJECT_ROOT / "corpus"))),
        chunk_size=int(env("CHUNK_SIZE", "300")),
        chunk_overlap=int(env("CHUNK_OVERLAP", "50")),
        top_k=int(env("TOP_K", "5")),
        min_similarity=float(env("MIN_SIMILARITY", "0.30")),
        gemini_api_key=env("GEMINI_API_KEY", ""),
        gemini_model=env("GEMINI_MODEL", "gemini-2.5-flash"),
        ollama_url=env("OLLAMA_URL", ""),
        ollama_model=env("OLLAMA_MODEL", "llama3.2"),
    )


def collection_name(chunk_size: int, overlap: int) -> str:
    return f"s{chunk_size}_o{overlap}"
