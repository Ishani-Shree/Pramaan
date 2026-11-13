# Pramaan — Cited, Self-Evaluating RAG over Technical Docs

*Pramaan (प्रमाण) — "proof / evidence".*

A retrieval-augmented question-answering system over my GitHub project READMEs.
Every answer cites the chunks it came from, the system abstains when the documents
don't contain the answer, and it ships with an evaluation harness.

> 🚧 Work in progress. Full setup, architecture and results coming soon.

## Quick start (so far)

```bash
cp .env.example .env          # then fill in GEMINI_API_KEY
docker compose up -d          # Postgres 16 + pgvector
```
