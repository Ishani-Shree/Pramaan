"""Shared test fixtures.

No network, no model download, no LLM:
  * FakeEmbedder: deterministic bag-of-words hashing into 384 dims, so texts
    sharing words are similar, and texts sharing none have similarity 0.
  * FakeLLM: returns scripted replies and records every prompt it received.

Database tests use a separate database whose name MUST end in "_test"
(the fixtures refuse anything else, so a test can never wipe real data).
  * TEST_DATABASE_URL picks it (default: the Docker DB on port 5434).
  * If it doesn't exist yet, it is created.
  * If Postgres isn't reachable, DB tests are skipped locally, but fail
    when PRAMAAN_REQUIRE_DB=1 (set in CI, so CI can't silently skip them).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from app.db import apply_schema, connect
from app.embeddings import EMBEDDING_DIM

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql://pramaan:pramaan@localhost:5434/pramaan_test"
)
REQUIRE_DB = os.getenv("PRAMAAN_REQUIRE_DB") == "1"


# ---------------------------------------------------------------- fakes

class FakeEmbedder:
    def __init__(self):
        self.calls: list[list[str]] = []

    def embed(self, texts):
        self.calls.append(list(texts))
        out = np.zeros((len(texts), EMBEDDING_DIM), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIM
                out[i, bucket] += 1.0
            norm = np.linalg.norm(out[i])
            if norm:
                out[i] /= norm
            else:
                out[i, 0] = 1.0  # avoid a zero vector (cosine undefined)
        return out


class FakeLLM:
    name = "fake"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def generate(self, system: str, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.replies:
            raise AssertionError("FakeLLM called more times than scripted")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply(prompt) if callable(reply) else reply


def chunk_ids_in(prompt: str) -> list[int]:
    return [int(x) for x in re.findall(r"\[chunk (\d+)\]", prompt)]


def cite_first(text: str = "Alpha listens on port 7001."):
    """A FakeLLM reply that cites the first chunk shown in the prompt."""
    def reply(prompt: str) -> str:
        return json.dumps(
            {"abstained": False, "claims": [{"text": text, "chunk_ids": [chunk_ids_in(prompt)[0]]}]}
        )
    return reply


@pytest.fixture
def embedder():
    return FakeEmbedder()


# ---------------------------------------------------------------- corpus

ALPHA = """# Alpha

Alpha is a job queue service.

## Setup

Install alpha with pip. The default port is 7001.

## Storage

Alpha stores jobs in Redis with append-only file persistence.
"""

BETA = """# Beta

Beta is a dashboard for weather data.

## Charts

Beta draws rainfall charts with matplotlib.
"""


@pytest.fixture
def corpus_dir(tmp_path: Path) -> Path:
    d = tmp_path / "corpus"
    d.mkdir()
    (d / "alpha.md").write_text(ALPHA, encoding="utf-8")
    (d / "beta.md").write_text(BETA, encoding="utf-8")
    return d


# ---------------------------------------------------------------- database

def _prepare_test_db(url: str) -> str | None:
    """Return None if ready, else the reason it isn't."""
    dbname = conninfo_to_dict(url).get("dbname", "")
    if not dbname.endswith("_test"):
        pytest.exit(f"Refusing to run tests against {dbname!r}: name must end in '_test'.", 2)
    try:
        psycopg.connect(url, connect_timeout=3).close()
    except psycopg.OperationalError as exc:
        if "does not exist" not in str(exc):
            return str(exc).strip().splitlines()[0]
        admin = make_conninfo(url, dbname="postgres")
        with psycopg.connect(admin, autocommit=True, connect_timeout=3) as c:
            c.execute(f'CREATE DATABASE "{dbname}"')
    with connect(url) as conn:
        apply_schema(conn)
    return None


@pytest.fixture(scope="session")
def test_db_url() -> str:
    problem = _prepare_test_db(TEST_DB_URL)
    if problem:
        message = f"test database unavailable ({TEST_DB_URL}): {problem}"
        if REQUIRE_DB:
            pytest.fail(message)
        pytest.skip(message)
    return TEST_DB_URL


@pytest.fixture
def conn(test_db_url):
    """A connection to an empty chunks table."""
    with connect(test_db_url) as c:
        c.execute("TRUNCATE chunks RESTART IDENTITY")
        c.commit()
        yield c
