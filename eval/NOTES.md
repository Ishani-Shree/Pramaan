# Evaluation notes

## Final run

`eval/results/` holds the final run (2026-11-13, `ollama:qwen2.5:7b` on an RTX 4060 Laptop GPU,
`num_ctx=16384`, laptop kept awake). Server log: 0 prompt truncations. Windows log: 0 standby events.

## Grading decision: the answer key was not changed after seeing answers

Two answers fail only on the exact key fact `delayed` (q13), though they describe a delayed job:

- `s300_o50_hybrid` q13: "adds a BullMQ job with `delay = scheduledAt − now`"
- `s800_o50_hybrid` q13: "uses BullMQ … jobs added to Redis and promoted to waiting when due"

They are counted as failures. Editing the key after seeing the outputs would inflate the scores.
This is a known limit of keyword-based grading: it misses correct paraphrases.

## Runs that were discarded (kept in `results/archive_*`)

1. `archive_2026-11-13_truncated_ctx`: Ollama's default context (2,048 tokens) silently cut
   ~4.6k–7.2k-token prompts for 800-word chunks to their last 2,050 tokens, removing the system
   prompt. 800-word configs scored 0% correct. The answer checks (JSON schema + citations) turned
   every malformed reply into an abstention: 0 wrong answers were returned.
2. `archive_2026-11-13_run2_sleep`: context fixed, but the laptop entered Modern Standby for
   39 minutes during one request, so latencies are invalid. Correctness matched the final run
   (118/120 answers word-for-word identical), which is a run-to-run stability check.

## Correction made during analysis

q14 (300-word configs) looked like a chunk-level retrieval miss, because the table row with the
default `2000` was not retrieved. The context-recall check showed that retrieved chunks #25/#26 say
"one send per 2 s", so the model had the fact. It is a generation miss.
