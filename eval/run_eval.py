"""Run the evaluation: every question x every config, then score.

    python -m eval.run_eval                      # all 4 configs
    python -m eval.run_eval --sizes 300 --modes hybrid
    python -m eval.run_eval --fresh              # ignore cached answers
    python -m eval.run_eval --sleep 6            # throttle (Gemini free tier)

Raw answers are cached per config in eval/results/raw_<config>.jsonl, so an
interrupted run (rate limit, Ctrl+C) resumes where it stopped. A cached answer
whose reason is llm_error is retried, because that was an outage, not an answer.

Outputs (eval/results/):
    per_question.csv   one row per (config, question)
    summary.csv        one row per config
    summary.md         the markdown table + failure list
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from app.answer import answer_question
from app.config import PROJECT_ROOT, collection_name, get_settings
from app.db import apply_schema, connect
from app.embeddings import SentenceTransformerEmbedder
from app.ingest import ingest_corpus
from app.llm import build_llm
from eval.scoring import median, missing_facts, percentile

EVAL_DIR = PROJECT_ROOT / "eval"
RESULTS_DIR = EVAL_DIR / "results"
CITATION_FAILURES = {"invalid_citation", "uncited_claim"}


def keep_awake() -> None:
    """Stop Windows from sleeping while the eval runs (like a video player
    does). Lasts only while this process lives; no power settings change.
    Found the hard way: Modern Standby paused one answer for 39 minutes and
    the 'latency' became 2,350,270 ms."""
    if platform.system() != "Windows":
        return
    import ctypes

    # On Modern Standby laptops the system sleeps when the display turns off,
    # so the display must be kept on too. Closing the lid still sleeps.
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)


def load_questions(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_cache(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["id"]: r for r in rows if r.get("reason") != "llm_error"}


def grade(q: dict, r: dict, context: str) -> dict:
    """Add the judgement fields to one raw result. `context` is the text of
    the chunks that were retrieved (what the LLM was shown)."""
    g = dict(r)
    if q["answerable"]:
        g["hit_at_k"] = q["expected_source_file"] in r["retrieved_files"]
        g["hit_at_1"] = bool(r["retrieved_files"]) and r["retrieved_files"][0] == q["expected_source_file"]
        # Context recall: were the key facts in the retrieved chunks at all?
        # File-level hit@k can't see this: the right file can be retrieved
        # while the one chunk holding the number is not.
        g["facts_not_in_context"] = missing_facts(context, q["key_facts"])
        g["context_recall"] = not g["facts_not_in_context"]
        g["missing_facts"] = [] if r["abstained"] else missing_facts(r["answer"], q["key_facts"])
        g["correct"] = (not r["abstained"]) and not g["missing_facts"]
        if g["correct"]:
            g["failure"] = ""
        elif not g["hit_at_k"]:
            g["failure"] = "retrieval_miss:file"
        elif r["abstained"]:
            g["failure"] = f"abstained:{r['reason']}"
        elif any(f in g["facts_not_in_context"] for f in g["missing_facts"]):
            g["failure"] = "retrieval_miss:chunk"  # the fact was never shown to the model
        else:
            g["failure"] = "generation_miss"  # the model saw the fact and left it out
    else:
        g["hit_at_k"] = g["hit_at_1"] = g["context_recall"] = None
        g["facts_not_in_context"] = []
        g["missing_facts"] = []
        g["correct"] = r["abstained"]  # the right behaviour is to abstain
        g["failure"] = "" if r["abstained"] else "answered_unanswerable"
    return g


def summarize(config: str, graded: list[dict], questions: dict[str, dict]) -> dict:
    ans = [g for g in graded if questions[g["id"]]["answerable"]]
    una = [g for g in graded if not questions[g["id"]]["answerable"]]
    lat = [g["latency_ms"] for g in graded]
    pct = lambda n, d: round(100 * n / d, 1) if d else 0.0
    return {
        "config": config,
        "hit@5_%": pct(sum(g["hit_at_k"] for g in ans), len(ans)),
        "hit@1_%": pct(sum(g["hit_at_1"] for g in ans), len(ans)),
        "context_recall_%": pct(sum(g["context_recall"] for g in ans), len(ans)),
        "correct_%": pct(sum(g["correct"] for g in ans), len(ans)),
        "abstain_unans_%": pct(sum(g["abstained"] for g in una), len(una)),
        "wrong_unans_%": pct(sum(not g["abstained"] for g in una), len(una)),
        "false_abstain_%": pct(sum(g["abstained"] for g in ans), len(ans)),
        "citation_fail": sum(g["reason"] in CITATION_FAILURES for g in graded),
        "invalid_json": sum(g["reason"] == "invalid_json" for g in graded),
        "llm_errors": sum(g["reason"] == "llm_error" for g in graded),
        "median_ms": round(median(lat)),
        "p95_ms": round(percentile(lat, 95)),
        "n_answerable": len(ans),
        "n_unanswerable": len(una),
    }


def markdown_table(rows: list[dict]) -> str:
    cols = [
        ("config", "Config"), ("hit@5_%", "Hit@5"), ("hit@1_%", "Hit@1"),
        ("context_recall_%", "Context recall"), ("correct_%", "Correct"), ("abstain_unans_%", "Abstain (unans.)"),
        ("wrong_unans_%", "Wrong (unans.)"), ("false_abstain_%", "False abstain"),
        ("citation_fail", "Citation fails"), ("median_ms", "Median ms"), ("p95_ms", "p95 ms"),
    ]
    pctcols = {"hit@5_%", "hit@1_%", "context_recall_%", "correct_%", "abstain_unans_%", "wrong_unans_%", "false_abstain_%"}
    out = ["| " + " | ".join(h for _, h in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(f"{r[k]}%" if k in pctcols else str(r[k]) for k, _ in cols) + " |")
    return "\n".join(out)


def failure_lines(config: str, graded: list[dict], questions: dict[str, dict]) -> list[str]:
    lines = []
    for g in graded:
        if g["correct"]:
            continue
        q = questions[g["id"]]
        if g["failure"] == "retrieval_miss:file":
            why = f"expected {q['expected_source_file']} not in top-k {sorted(set(g['retrieved_files']))}"
        elif g["failure"] == "retrieval_miss:chunk":
            why = (f"right file, but {g['facts_not_in_context']} not in any retrieved chunk "
                   f"{g['retrieved_ids']}: \"{g['answer'][:140]}\"")
        elif g["failure"] == "generation_miss":
            why = f"facts were in context, answer lacks {g['missing_facts']}: \"{g['answer'][:140]}\""
        elif g["failure"] == "answered_unanswerable":
            why = f"should abstain, answered: \"{g['answer'][:160]}\""
        else:
            why = f"{g['failure']} (top sim {g['top_similarity']:.3f}){' - ' + g['detail'] if g.get('detail') else ''}"
        lines.append(f"- `{config}` **{g['id']}** [{g['failure']}] {q['question']}  \n  → {why}")
    return lines


def main() -> None:
    s = get_settings()
    p = argparse.ArgumentParser(description="Run the Pramaan evaluation.")
    p.add_argument("--questions", default=str(EVAL_DIR / "questions.jsonl"))
    p.add_argument("--sizes", type=int, nargs="+", default=[300, 800])
    p.add_argument("--modes", nargs="+", default=["vector", "hybrid"], choices=["vector", "hybrid", "keyword"])
    p.add_argument("--overlap", type=int, default=s.chunk_overlap)
    p.add_argument("-k", type=int, default=s.top_k)
    p.add_argument("--sleep", type=float, default=0.0, help="seconds to wait after each LLM call")
    p.add_argument("--fresh", action="store_true", help="ignore cached raw answers")
    args = p.parse_args()

    keep_awake()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    questions = load_questions(Path(args.questions))
    by_id = {q["id"]: q for q in questions}

    embedder = SentenceTransformerEmbedder(s.embedding_model)
    llm = build_llm(s)
    meta = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "llm": llm.name, "embedding_model": s.embedding_model, "k": args.k,
        "min_similarity": s.min_similarity, "overlap": args.overlap,
        "ollama_num_ctx": s.ollama_num_ctx if s.ollama_url else None,
        "questions": len(questions), "machine": platform.platform(),
    }
    print(json.dumps(meta, indent=2))

    all_graded: list[dict] = []
    summaries: list[dict] = []
    with connect(s.database_url) as conn:
        apply_schema(conn)
        for size in args.sizes:
            report = ingest_corpus(conn, embedder, s.corpus_dir, size, args.overlap)  # idempotent
            print(f"\ningest {report.collection}: {report.chunks} chunks "
                  f"(inserted {report.inserted}, skipped {report.skipped}, deleted {report.deleted})")
            collection = collection_name(size, args.overlap)

            # Warm-up: load the LLM into memory so the first timed question
            # doesn't carry the model's cold-start cost.
            try:
                llm.generate("Reply with JSON only.", 'Return {"ok": true}')
            except Exception as exc:
                print(f"warm-up failed: {exc}")

            for mode in args.modes:
                config = f"{collection}_{mode}"
                cache_path = RESULTS_DIR / f"raw_{config}.jsonl"
                cache = {} if args.fresh else load_cache(cache_path)
                if args.fresh and cache_path.exists():
                    cache_path.unlink()
                print(f"\n== {config}  ({len(cache)} cached)")
                graded = []
                for q in questions:
                    if q["id"] in cache:
                        raw = cache[q["id"]]
                    else:
                        res = answer_question(conn, embedder, llm, q["question"], collection,
                                              args.k, mode, s.min_similarity)
                        raw = {"id": q["id"], "config": config, "llm": getattr(llm, "last_used", llm.name),
                               **asdict(res)}
                        raw["sources"] = [src["chunk_id"] for src in raw["sources"]]
                        with cache_path.open("a", encoding="utf-8") as f:
                            f.write(json.dumps(raw, ensure_ascii=False) + "\n")
                        if res.llm_calls and args.sleep:
                            time.sleep(args.sleep)
                    texts = dict(conn.execute(
                        "SELECT id, text FROM chunks WHERE id = ANY(%s)", (raw["retrieved_ids"],)
                    ).fetchall())
                    g = grade(q, raw, "\n".join(texts.get(i, "") for i in raw["retrieved_ids"]))
                    graded.append(g)
                    mark = "PASS" if g["correct"] else "FAIL"
                    print(f"  {q['id']} {mark:<4} {raw['latency_ms']:>6}ms  {raw['reason'] or 'answered':<17} {g['failure']}")
                summaries.append(summarize(config, graded, by_id))
                all_graded.extend(graded)

    # ---- write outputs ----
    fields = ["config", "id", "question", "answerable", "expected_source_file", "correct", "failure",
              "hit_at_k", "hit_at_1", "context_recall", "facts_not_in_context", "abstained", "reason", "top_similarity", "latency_ms", "llm_calls",
              "missing_facts", "retrieved_files", "sources", "answer", "detail", "llm"]
    with (RESULTS_DIR / "per_question.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for g in all_graded:
            q = by_id[g["id"]]
            w.writerow({**g, "question": q["question"], "answerable": q["answerable"],
                        "expected_source_file": q["expected_source_file"],
                        "missing_facts": json.dumps(g["missing_facts"]),
                        "facts_not_in_context": json.dumps(g["facts_not_in_context"]),
                        "retrieved_files": json.dumps(g["retrieved_files"]),
                        "sources": json.dumps(g["sources"])})
    with (RESULTS_DIR / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summaries[0]))
        w.writeheader()
        w.writerows(summaries)

    table = markdown_table(summaries)
    failures = []
    for sm in summaries:
        failures += failure_lines(sm["config"], [g for g in all_graded if g["config"] == sm["config"]], by_id)
    md = (f"# Pramaan evaluation\n\n```json\n{json.dumps(meta, indent=2)}\n```\n\n{table}\n\n"
          f"Hit@5 / Hit@1 / Correct / False abstain: over {summaries[0]['n_answerable']} answerable questions. "
          f"Abstain / Wrong (unans.): over {summaries[0]['n_unanswerable']} unanswerable questions. "
          f"Latency: all questions, including fast abstentions.\n\n## Failed questions\n\n"
          + ("\n".join(failures) or "None") + "\n")
    (RESULTS_DIR / "summary.md").write_text(md, encoding="utf-8")
    (RESULTS_DIR / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print("\n" + table)
    print(f"\n{len(failures)} failures — see eval/results/summary.md")


if __name__ == "__main__":
    main()
