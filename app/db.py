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
    register_vector(conn)  # lets us pass numpy arrays as vector values
    return conn
