# Pramaan evaluation

```json
{
  "run_at": "2026-11-13T17:04:39+00:00",
  "llm": "ollama:qwen2.5:7b",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "k": 5,
  "min_similarity": 0.3,
  "overlap": 50,
  "ollama_num_ctx": 16384,
  "questions": 30,
  "machine": "Windows-10-10.0.26300-SP0"
}
```

| Config | Hit@5 | Hit@1 | Context recall | Correct | Abstain (unans.) | Wrong (unans.) | False abstain | Citation fails | Median ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| s300_o50_vector | 100.0% | 100.0% | 100.0% | 80.0% | 100.0% | 0.0% | 0.0% | 0 | 6602 | 11086 |
| s300_o50_hybrid | 100.0% | 100.0% | 100.0% | 88.0% | 100.0% | 0.0% | 0.0% | 0 | 8306 | 11532 |
| s800_o50_vector | 100.0% | 100.0% | 100.0% | 96.0% | 100.0% | 0.0% | 0.0% | 0 | 10082 | 12379 |
| s800_o50_hybrid | 100.0% | 96.0% | 100.0% | 96.0% | 100.0% | 0.0% | 0.0% | 0 | 10214 | 12645 |

Hit@5 / Hit@1 / Correct / False abstain: over 25 answerable questions. Abstain / Wrong (unans.): over 5 unanswerable questions. Latency: all questions, including fast abstentions.

## Failed questions

- `s300_o50_vector` **q04** [generation_miss] Why does the Energy-Aware GPU project not trust the NVML hardware energy counter?  
  → facts were in context, answer lacks ['325', '140']: "The Energy-Aware GPU project does not fully trust the NVML hardware energy counter because it is unreliable on the tested RTX 4060 Laptop GP"
- `s300_o50_vector` **q13** [generation_miss] How does the ReachInbox scheduler schedule emails without using cron?  
  → facts were in context, answer lacks ['delayed', 'BullMQ']: "There is no cron or polling loop. [23]"
- `s300_o50_vector` **q14** [generation_miss] What is the default minimum delay between two sends from the same sender in ReachInbox?  
  → facts were in context, answer lacks [['2000', '2 s', '2s', '2 seconds', 'two seconds']]: "The minimum delay between sends is a second Lua script that keeps a per-sender 'next free slot' timestamp. Each send reserves `max(now, next"
- `s300_o50_vector` **q16** [generation_miss] Under what circumstance can ReachInbox send the same email twice?  
  → facts were in context, answer lacks ['SMTP', ['SENT', 'at least once']]: "ReachInbox does not drop or fail jobs for rate limiting, and deferral doesn't use up a retry attempt. [25]"
- `s300_o50_vector` **q18** [generation_miss] How many API tests does ShopZone have, and how many of them fail on the original code?  
  → facts were in context, answer lacks ['22']: "The test suite has **51 API tests**. [35][37]"
- `s300_o50_hybrid` **q13** [generation_miss] How does the ReachInbox scheduler schedule emails without using cron?  
  → facts were in context, answer lacks ['delayed']: "For each email it adds a BullMQ job with `delay = scheduledAt − now` and `jobId = email-<emailId>`. Jobs are added with `addBulk` in chunks "
- `s300_o50_hybrid` **q14** [generation_miss] What is the default minimum delay between two sends from the same sender in ReachInbox?  
  → facts were in context, answer lacks [['2000', '2 s', '2s', '2 seconds', 'two seconds']]: "The minimum delay between sends is handled by a second Lua script that keeps a per-sender 'next free slot' timestamp. Each send reserves `ma"
- `s300_o50_hybrid` **q18** [generation_miss] How many API tests does ShopZone have, and how many of them fail on the original code?  
  → facts were in context, answer lacks ['22']: "The test suite has **51 API tests**. [35]"
- `s800_o50_vector` **q16** [generation_miss] Under what circumstance can ReachInbox send the same email twice?  
  → facts were in context, answer lacks ['SMTP']: "ReachInbox ensures idempotency at multiple levels to prevent sending the same email twice: [62] - The `Idempotency-Key` header on campaign c"
- `s800_o50_hybrid` **q13** [generation_miss] How does the ReachInbox scheduler schedule emails without using cron?  
  → facts were in context, answer lacks ['delayed']: "ReachInbox uses BullMQ to schedule emails, with jobs added to Redis and promoted to waiting when due, without a cron or polling loop. [62]"
