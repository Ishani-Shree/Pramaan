# Pramaan — Cited, Self-Evaluating RAG over Technical Docs

[![CI](https://github.com/Ishani-Shree/Pramaan/actions/workflows/ci.yml/badge.svg)](https://github.com/Ishani-Shree/Pramaan/actions/workflows/ci.yml)

*Pramaan (प्रमाण): "proof, evidence".*

Pramaan answers questions about my GitHub projects using only their READMEs. Every claim in an
answer cites the chunk it came from, and those citations are checked in code. If the documents
don't contain the answer, Pramaan says so instead of guessing. It comes with an evaluation
harness: the numbers below come from runs on my laptop and can be re-checked from the raw
outputs in [`eval/results/`](eval/results/).

```http
POST /ask  {"question": "Which GPU was used for the energy experiments?", "mode": "hybrid"}

{"answer": "The RTX 4060 Laptop GPU was used for the energy experiments. [9]",
 "sources": [{"source_file": "Energy_Aware_GPU.md", "heading": "...", "chunk_id": 9}],
 "abstained": false, "latency_ms": 3943, "reason": null, "top_similarity": 0.5107}

POST /ask  {"question": "What license does ShopZone use?"}
{"answer": "I can't answer that from the indexed documents.", "sources": [],
 "abstained": true, "reason": "model_abstained", ...}
```

## Architecture

```
                 INGEST (idempotent)                                  ASK
 corpus/*.md, *.pdf                                    question
      │ loader (pypdf: one "## Page N" per page)          │
      ▼                                                   ▼
 heading-aware chunker ── 300 or 800 words,         embed (MiniLM, 384-d)
      │                   50-word overlap                 │
      ▼                                                   ▼
 sha256(collection, file, heading, text) ──┐   ┌── vector search (cosine, HNSW)
      │ already stored? skip (no embedding) │   │   keyword search (tsvector, OR terms)
      ▼                                     │   │   hybrid = reciprocal rank fusion
 embed new chunks only                      │   │        │
      │                                     ▼   │        ▼
      └──► PostgreSQL 16 + pgvector ◄───────────┘   best similarity < 0.30 ? ── abstain (no LLM call)
           chunks(collection, source_file,                   │
                  heading, text, content_hash UNIQUE,        ▼
                  embedding vector(384), tsv)       LLM (local qwen2.5:7b via Ollama,
                                                         or Gemini): JSON claims + chunk ids
                                                             │
                                          Pydantic schema ✗ ── retry once ✗ ── abstain
                                          cites an id not retrieved / uncited claim ── abstain
                                                             │
                                                             ▼
                                          {answer, sources, abstained, latency_ms, reason}
```

| Module | Role |
|---|---|
| [`app/chunker.py`](app/chunker.py) | Heading split → pack small sections → overlapping windows for long ones |
| [`app/ingest.py`](app/ingest.py) | Hash, embed only new chunks, insert, delete stale ones, in one transaction |
| [`app/retrieval.py`](app/retrieval.py) | Vector, keyword and hybrid (RRF) search |
| [`app/answer.py`](app/answer.py) | Prompt, JSON validation, citation checks, every abstention path |
| [`app/llm.py`](app/llm.py) | Gemini and Ollama clients with fallback |
| [`eval/run_eval.py`](eval/run_eval.py) | Runs every question in every config, grades, writes CSV + markdown |

## Results

30 questions ([`eval/questions.jsonl`](eval/questions.jsonl)): 25 answerable, each with the
README that holds the answer and 1–3 key facts the answer must contain, plus 5 whose answer is in
no README. Run on 2026-11-13 with `qwen2.5:7b` (Ollama, RTX 4060 Laptop GPU), `all-MiniLM-L6-v2`
embeddings and k = 5.

| Config | Hit@5 | Hit@1 | Context recall | **Correct** | Abstain (unans.) | Wrong (unans.) | False abstain | Median latency | p95 latency |
|---|---|---|---|---|---|---|---|---|---|
| 300 words, vector | 100% | 100% | 100% | **80%** | 100% | 0% | 0% | 6.6 s | 11.1 s |
| 300 words, hybrid | 100% | 100% | 100% | **88%** | 100% | 0% | 0% | 8.3 s | 11.5 s |
| 800 words, vector | 100% | 100% | 100% | **96%** | 100% | 0% | 0% | 10.1 s | 12.4 s |
| 800 words, hybrid | 100% | 96% | 100% | **96%** | 100% | 0% | 0% | 10.2 s | 12.6 s |

- **Hit@5 / Hit@1**: the expected README is among the top 5 chunks / is the top chunk.
- **Context recall**: every key fact appears somewhere in the retrieved chunks, i.e. the model was
  shown what it needed.
- **Correct**: the answer contains every key fact (case-insensitive; `1,326` = `1326`,
  `EfficientNet B2` = `EfficientNet-B2`).
- **Abstain / Wrong (unans.)**: out of the 5 unanswerable questions.
- **False abstain**: said "I don't know" when the answer was in the corpus.
- Latency covers all 30 questions, including fast abstentions.

**What the numbers say**

- **Retrieval was never the problem on this set.** Every failure in every config is a generation
  miss: the facts were in the context and the model left some out.
- **800-word chunks gave the best answers (96% vs 80–88%), but were slower in every valid run**
  (median +1.5 to +3.5 s), because the model reads about 3× more text. With fewer, fuller chunks
  the facts the 7B model needs sit together. Best config: **800 words, vector** (ties hybrid on
  correctness, higher Hit@1).
- **Hybrid search helped at 300 words** (88% vs 80%) and made no difference at 800.
- **It never answered an unanswerable question** (5/5 abstentions in every config), never refused
  an answerable one, and never cited a chunk it wasn't given.
- **All 5 of those abstentions came from the model, not the similarity threshold.** The
  unanswerable questions are on-topic ("What F1 score does the microplastic model get on the Fiber
  class?") and scored 0.40–0.67, as high as answerable ones (0.37–0.77). The 0.30 threshold only
  catches clearly off-topic questions.
- 1 question = 4 percentage points. "96% vs 88%" is 2 questions, a signal rather than a proof.

Full failure list: [`eval/results/summary.md`](eval/results/summary.md). Notes on grading and on
discarded runs: [`eval/NOTES.md`](eval/NOTES.md).

### Three failures, and what they taught

**1. The LLM server silently threw away the instructions.** In the first evaluation run, both
800-word configs scored 0%. Ollama's server log showed `truncating input prompt limit=2050
prompt=5813`: Ollama's default context window is 2,048 tokens, and longer prompts are not
rejected. Ollama keeps the *last* 2,050 tokens and drops the start, which is where the system
prompt and rules are. The model answered things like `{"port": 3000}`. All 60 replies from those
two configs were caught by the checks and became abstentions (36 invalid JSON, 14 uncited
answers, 6 server errors, 4 model abstentions). **Zero wrong answers reached the user.** Fix:
`num_ctx=16384`, plus a client-side check that refuses an over-long prompt loudly instead of
letting it be cut. A regression test guards it ([`tests/test_llm.py`](tests/test_llm.py)). The
broken run is kept in [`eval/results/archive_2026-11-13_truncated_ctx/`](eval/results/).

**2. The model saw the fact and left it out (q18, 300-word configs).** *"How many API tests does
ShopZone have, and how many fail on the original code?"* The answer was "The test suite has
**51 API tests**. [35]". Chunk #35, which was retrieved and cited, also says "On the original
code, 22 of them fail". Context recall marks this as a generation miss, not a retrieval miss. The
two-part question was answered by half. At 800 words it was answered fully.

**3. The grader rejected a correct paraphrase (q13).** *"How does ReachInbox schedule emails
without cron?"* One answer was "adds a BullMQ job with `delay = scheduledAt − now`", which is a
delayed job, but the key fact requires the word `delayed`. I kept it as a failure: changing the
answer key after seeing outputs would inflate the scores. Keyword grading is cheap and
reproducible, but it under-counts correct paraphrases.

## Design decisions

**Heading-aware chunking, then packing.** Splitting at Markdown headings keeps each chunk about
one topic, so its embedding isn't a blur of two sections. Each chunk keeps its full heading path
(`ShopZone > Run locally > Tests`), which is also embedded, so a chunk "knows" its project even if
its text never names it. Small neighbouring sections are then packed up to N words, keeping
`### subheading` lines in the text: without packing, these READMEs give a median chunk of 76 words
and 300 vs 800 makes almost no difference (112 vs 109 chunks). Sections longer than N are cut
into windows with a 50-word overlap, so a sentence on a boundary appears whole in at least one
chunk. Lines starting with `#` inside code blocks are not treated as headings, and image-only
sections (screenshots) are dropped.

**Hybrid search with reciprocal rank fusion.** Vector search matches meaning ("job queue" finds
BullMQ). Postgres full-text search matches exact terms that a small embedding model handles
poorly (`NVML`, `RTX 4060`). RRF combines them using ranks only (`score = Σ 1/(60 + rank)`),
because cosine similarity and `ts_rank` are on different scales and can't be added. The keyword
query uses OR between terms: `plainto_tsquery` ANDs every word, so a natural question almost
never matches.

**Abstention at two levels.** (1) If even the best chunk's cosine similarity is below 0.30, the
corpus clearly doesn't cover the question, so Pramaan abstains *without calling the LLM*: "What is
the capital of France?" scores 0.09 and costs 16 ms. (2) Otherwise the model is told to abstain
when the chunks don't contain the answer. The evaluation shows why both are needed: a
similarity score measures *topic*, not *whether the answer is there*. "What license does ShopZone
use?" scores 0.48, and the five unanswerable questions scored 0.40–0.67, overlapping the
answerable ones (0.37–0.77). No threshold separates them, so level 2 did all the work there.

**Citations checked in code, per claim.** The model must return `{"claims": [{"text", "chunk_ids"}]}`.
Every claim needs at least one id, and every id must be one of the chunks actually retrieved.
Anything else becomes `abstained: true` with a reason (`invalid_citation`, `uncited_claim`), so
"cite every claim" is enforced, not just requested. Replies are validated with Pydantic. JSON mode
guarantees JSON, not the right fields. A bad reply gets one retry that names the error, then the
system abstains. Every abstention returns a machine-readable `reason`, which is what lets the
evaluation count failures by type.

**Idempotent ingest.** Each chunk's `content_hash` is a sha256 of collection, file, heading and
text, with a UNIQUE constraint. Ingest checks which hashes exist *before* embedding, so re-running
on unchanged files inserts 0 rows and embeds nothing. In one transaction it also deletes chunks
that are no longer produced: an edited README never leaves stale text to be cited, and a removed
README leaves the index. An empty corpus folder is refused rather than allowed to wipe the index.
`ON CONFLICT DO NOTHING` makes concurrent ingests safe.

**Built to be tested.** Code depends on small `Embedder` and `LLM` interfaces. The 75 tests use a
deterministic fake embedder and a scripted fake LLM: no network, no model download, no PyTorch in
CI. They refuse to run against any database not named `*_test`. Writing them found three bugs that
manual testing had missed: `POST /ingest` reported inserts but rolled them back on a fresh
database; the app could not start on a database without the `vector` extension; and a deleted
README stayed in the index.

## Run it

Requirements: Python 3.11, Docker, and either [Ollama](https://ollama.com) (local, no key) or a
free [Gemini API key](https://aistudio.google.com/apikey).

```powershell
git clone https://github.com/Ishani-Shree/Pramaan.git
cd Pramaan
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                # set GEMINI_API_KEY, or keep the Ollama defaults

docker compose up -d                # Postgres 16 + pgvector on localhost:5434

# LLM, if using Ollama:
ollama pull qwen2.5:7b

python scripts/fetch_corpus.py      # optional: corpus/ is already committed
python -m app.ingest --size 800     # embed + store (re-run: inserted=0)
uvicorn app.main:app --reload       # http://127.0.0.1:8000/docs
```

| Endpoint | |
|---|---|
| `POST /ingest` | `{"chunk_size": 800, "overlap": 50}` → inserted / skipped / deleted counts |
| `POST /search` | retrieval only, no LLM: see what `/ask` would be given |
| `POST /ask` | `{"question": "...", "k": 5, "mode": "vector" \| "hybrid"}` |

Other commands:

```powershell
python -m app.retrieval "How does ReachInbox use BullMQ?"   # compare vector / keyword / hybrid
python -m eval.run_eval                                     # 4 configs x 30 questions (~20 min on a laptop GPU)
python -m pytest -v                                         # 75 tests; creates pramaan_test automatically
```

The database uses host port **5434** so it doesn't clash with a local PostgreSQL on 5432.

## Limits

- **Small corpus:** 8 READMEs, 11,797 words: 53 chunks at 300 words, 20 at 800. At 800 words, the
  top 5 is a quarter of the whole index, which makes Hit@5 easy. Retrieval quality at scale is
  untested.
- **Questions written by me:** I wrote all 30 after reading the READMEs, often in their wording.
  Real users phrase things differently, so the 100% retrieval figures are optimistic.
- **Small evaluation:** 25 answerable questions (1 question = 4 points) and only 5 unanswerable
  ones. "100% abstention" means 5 out of 5.
- **Single LLM:** all reported results use one local 7B model (`qwen2.5:7b`). The Gemini path is
  implemented but was not evaluated.
- **Keyword grading** misses correct paraphrases (failure 3) and can accept a short number that
  appears by chance.
- **Latency is from one laptop GPU** and varies a lot between runs: with identical code, the
  300-word hybrid config had a 5.3 s median in two earlier runs and 8.3 s in the reported one.
  Treat latency differences of 1–2 s between configs as noise.
- The similarity threshold (0.30) was set from a handful of spot checks, not tuned. Tuning it on
  the 30 evaluation questions would have overfit. As measured, it never fired on the
  unanswerable questions: abstention on on-topic questions depends entirely on the model.
