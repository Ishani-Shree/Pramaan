"""Database connection helpers."""

from __future__ import annotations

import psycopg
from pgvector.psycopg import register_vector

from app.config import PROJECT_ROOT

SCHEMA_PATH = PROJECT_ROOT / "schema.sql"


def apply_schema(conn: psycopg.Connection) -> None:
    """Run schema.sql. Safe to repeat (IF NOT EXISTS everywhere). Needed where
    the Docker init script can't run, e.g. the CI service container."""
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def connect(database_url: str) -> psycopg.Connection:
    conn = psycopg.connect(database_url)
    # register_vector needs the `vector` type to exist already. On a brand-new
    # database (CI, a fresh hosted Postgres) nothing has created it yet, so
    # create the extension first. Safe to repeat.
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    register_vector(conn)  # lets us pass numpy arrays as vector values
    # Filtered ANN: with WHERE collection = ..., an HNSW scan may find its
    # nearest candidates in *other* collections, filter them out, and return
    # fewer than k rows. strict_order (pgvector >= 0.8) keeps scanning the
    # index until k matching rows are found, still in exact distance order.
    conn.execute("SET hnsw.iterative_scan = strict_order")
    conn.commit()
    return conn
