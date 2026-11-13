-- Pramaan schema. Safe to re-run (IF NOT EXISTS everywhere).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id            BIGSERIAL PRIMARY KEY,
    -- Which chunking config produced this row, e.g. "s300_o50". Lets several
    -- configs live side by side for the evaluation; retrieval filters on it.
    collection    TEXT        NOT NULL,
    source_file   TEXT        NOT NULL,
    heading       TEXT        NOT NULL DEFAULT '',
    chunk_index   INTEGER     NOT NULL,
    text          TEXT        NOT NULL,
    -- sha256 of (collection, source_file, heading, text): makes ingest idempotent.
    content_hash  TEXT        NOT NULL UNIQUE,
    -- all-MiniLM-L6-v2 produces 384-dimensional vectors.
    embedding     vector(384) NOT NULL,
    -- Full-text search column for hybrid retrieval (Step 5).
    -- GENERATED: Postgres keeps it in sync with heading + text automatically.
    tsv           tsvector GENERATED ALWAYS AS (
                      to_tsvector('english', coalesce(heading, '') || ' ' || text)
                  ) STORED,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Approximate nearest-neighbour index for cosine distance (the <=> operator).
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

-- Inverted index for keyword search.
CREATE INDEX IF NOT EXISTS chunks_tsv_gin
    ON chunks USING gin (tsv);

CREATE INDEX IF NOT EXISTS chunks_collection_source_idx
    ON chunks (collection, source_file);
