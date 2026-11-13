# Pramaan evaluation

```json
{
  "run_at": "2026-11-13T15:33:00+00:00",
  "llm": "ollama:qwen2.5:7b",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "k": 5,
  "min_similarity": 0.3,
  "overlap": 50,
  "questions": 30,
  "machine": "Windows-10-10.0.26300-SP0"
}
```

| Config | Hit@5 | Hit@1 | Correct | Abstain (unans.) | Wrong (unans.) | False abstain | Citation fails | Median ms | p95 ms |
|---|---|---|---|---|---|---|---|---|---|
| s300_o50_vector | 100.0% | 100.0% | 80.0% | 100.0% | 0.0% | 0.0% | 0 | 5307 | 6591 |
| s300_o50_hybrid | 100.0% | 100.0% | 88.0% | 100.0% | 0.0% | 0.0% | 0 | 5286 | 6931 |
| s800_o50_vector | 100.0% | 100.0% | 0.0% | 100.0% | 0.0% | 100.0% | 6 | 9198 | 13141 |
| s800_o50_hybrid | 100.0% | 96.0% | 0.0% | 100.0% | 0.0% | 100.0% | 8 | 9240 | 15857 |

Hit@5 / Hit@1 / Correct / False abstain: over 25 answerable questions. Abstain / Wrong (unans.): over 5 unanswerable questions. Latency: all questions, including fast abstentions.

## Failed questions

- `s300_o50_vector` **q04** Why does the Energy-Aware GPU project not trust the NVML hardware energy counter?  
  → answer lacks ['325', '140']: "The Energy-Aware GPU project does not fully trust the NVML hardware energy counter because it is unreliable on the tested RTX 4060 Laptop GPU. [6]"
- `s300_o50_vector` **q13** How does the ReachInbox scheduler schedule emails without using cron?  
  → answer lacks ['delayed', 'BullMQ']: "There is no cron or polling loop. [23]"
- `s300_o50_vector` **q14** What is the default minimum delay between two sends from the same sender in ReachInbox?  
  → answer lacks [['2000', '2 s', '2s', '2 seconds', 'two seconds']]: "The minimum delay between sends is a second Lua script that keeps a per-sender 'next free slot' timestamp. Each send reserves `max(now, nextFree)` and pushes `n"
- `s300_o50_vector` **q16** Under what circumstance can ReachInbox send the same email twice?  
  → answer lacks ['SMTP', ['SENT', 'at least once']]: "ReachInbox does not drop or fail jobs for rate limiting, and deferral doesn't use up a retry attempt. [25]"
- `s300_o50_vector` **q18** How many API tests does ShopZone have, and how many of them fail on the original code?  
  → answer lacks ['22']: "The test suite has **51 API tests**. [35][37]"
- `s300_o50_hybrid` **q13** How does the ReachInbox scheduler schedule emails without using cron?  
  → answer lacks ['delayed']: "For each email it adds a BullMQ job with `delay = scheduledAt − now` and `jobId = email-<emailId>`. Jobs are added with `addBulk` in chunks of 500, so 1,000+ re"
- `s300_o50_hybrid` **q14** What is the default minimum delay between two sends from the same sender in ReachInbox?  
  → answer lacks [['2000', '2 s', '2s', '2 seconds', 'two seconds']]: "The minimum delay between sends is handled by a second Lua script that keeps a per-sender 'next free slot' timestamp. Each send reserves `max(now, nextFree)` an"
- `s300_o50_hybrid` **q18** How many API tests does ShopZone have, and how many of them fail on the original code?  
  → answer lacks ['22']: "The test suite has **51 API tests**. [35]"
- `s800_o50_vector` **q01** What does Parakh stress-test, and what kind of phone calls does it simulate?  
  → abstained:invalid_json (top sim 0.631) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}]
- `s800_o50_vector` **q02** In Parakh, how did the pass rate on held-out scenarios change after making the agent tolerate sound-alike spellings?  
  → abstained:invalid_json (top sim 0.639) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'Pass rate on held-out scenarios': '-5%'}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}
- `s800_o50_vector` **q03** Which Whisper model size was the most accurate setup in Parakh, and what was its overall pass rate?  
  → abstained:invalid_json (top sim 0.459) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'model_size': 'large', 'pass_rate': 92.3}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}
- `s800_o50_vector` **q04** Why does the Energy-Aware GPU project not trust the NVML hardware energy counter?  
  → abstained:llm_error (top sim 0.618) - ollama:qwen2.5:7b: Server error '500 Internal Server Error' for url 'http://localhost:11434/api/chat'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500
- `s800_o50_vector` **q05** In the measured scheduling run of the Energy-Aware GPU project, what window energy did the performance and energy-aware policies use?  
  → abstained:uncited_claim (top sim 0.744) - model answered but gave no claims
- `s800_o50_vector` **q06** According to the Energy-Aware GPU project, which knob is needed for energy-aware scheduling to beat race-to-idle?  
  → abstained:invalid_json (top sim 0.686) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'answer': 'batch size'}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}]
- `s800_o50_vector` **q07** What two fusion strategies does the investment scam detector offer?  
  → abstained:invalid_json (top sim 0.564) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'answer': ['Sensitivity', 'Show me everything']}, 'url': 'https://errors.pydantic.dev/2.14/v/mi
- `s800_o50_vector` **q08** What ROC-AUC does the investment scam detector reach with the URL expert added?  
  → abstained:uncited_claim (top sim 0.495) - model answered but gave no claims
- `s800_o50_vector` **q09** In the investment scam detector, which classifier handles the image modality and what extracts the visual features?  
  → abstained:model_abstained (top sim 0.519)
- `s800_o50_vector` **q10** What risk levels can the Diabetes Insight Dashboard return?  
  → abstained:model_abstained (top sim 0.723)
- `s800_o50_vector` **q11** Which backend framework and machine learning library does the Diabetes Insight Dashboard use?  
  → abstained:invalid_json (top sim 0.709) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}]
- `s800_o50_vector` **q12** On which port does the Diabetes Insight Dashboard frontend dev server run?  
  → abstained:uncited_claim (top sim 0.501) - model answered but gave no claims
- `s800_o50_vector` **q13** How does the ReachInbox scheduler schedule emails without using cron?  
  → abstained:llm_error (top sim 0.562) - ollama:qwen2.5:7b: Server error '500 Internal Server Error' for url 'http://localhost:11434/api/chat'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500
- `s800_o50_vector` **q14** What is the default minimum delay between two sends from the same sender in ReachInbox?  
  → abstained:invalid_json (top sim 0.440) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'answer': 'The default minimum delay between two sends from the same sender in ReachInbox is 20
- `s800_o50_vector` **q15** What happens to email search in ReachInbox when Elasticsearch is down?  
  → abstained:invalid_json (top sim 0.473) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'answer': 'If Elasticsearch is down, search falls back to a Postgres `ILIKE` query and sending 
- `s800_o50_vector` **q16** Under what circumstance can ReachInbox send the same email twice?  
  → abstained:invalid_json (top sim 0.371) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'answer': 'ReachInbox will send the same email twice if the same Idempotency-Key header is used
- `s800_o50_vector` **q17** How does ShopZone stop stock from going negative when many buyers check out at once?  
  → abstained:invalid_json (top sim 0.501) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'type': 'answer', 'response': 'ShopZone handles stock negatives by ensuring that the stock quan
- `s800_o50_vector` **q18** How many API tests does ShopZone have, and how many of them fail on the original code?  
  → abstained:invalid_json (top sim 0.496) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'total_api_tests': 51, 'failed_tests_on_original_code': 22}, 'url': 'https://errors.pydantic.de
- `s800_o50_vector` **q19** Which external services does ShopZone use for geolocation and exchange rates?  
  → abstained:uncited_claim (top sim 0.446) - model answered but gave no claims
- `s800_o50_vector` **q20** Which model architecture does the Underwater Microplastic Detection system use?  
  → abstained:invalid_json (top sim 0.681) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}]
- `s800_o50_vector` **q21** What validation accuracy does the underwater microplastic classifier report?  
  → abstained:invalid_json (top sim 0.672) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}]
- `s800_o50_vector` **q22** Which microplastic class is mapped to the Critical pollution state?  
  → abstained:invalid_json (top sim 0.409) - JSON has the wrong shape: [{'type': 'bool_parsing', 'loc': ('abstained',), 'msg': 'Input should be a valid boolean, unable to interpret input', 'input': 'Class C', 'url': 'https://errors.pydantic.dev/
- `s800_o50_vector` **q23** What signals make up Watermark's composite score for a stock move?  
  → abstained:llm_error (top sim 0.547) - ollama:qwen2.5:7b: Server error '500 Internal Server Error' for url 'http://localhost:11434/api/chat'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500
- `s800_o50_vector` **q24** In Watermark, what score opens an event and what score keeps an existing event alive?  
  → abstained:invalid_json (top sim 0.485) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'answer': 'A score must exceed 50 to open an event but only fall below 35 to keep one alive.'},
- `s800_o50_vector` **q25** How much did Watermark's median digest latency drop after collapsing five queries into two?  
  → abstained:uncited_claim (top sim 0.656) - model answered but gave no claims
- `s800_o50_hybrid` **q01** What does Parakh stress-test, and what kind of phone calls does it simulate?  
  → abstained:invalid_json (top sim 0.631) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'stress-test': "Parakh's stress test simulates high-volume phone calls to the API, with up to 1
- `s800_o50_hybrid` **q02** In Parakh, how did the pass rate on held-out scenarios change after making the agent tolerate sound-alike spellings?  
  → abstained:invalid_json (top sim 0.639) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'answer': {'abstained': False, 'details': 'The pass rate on held-out scenarios improved by 5 pe
- `s800_o50_hybrid` **q03** Which Whisper model size was the most accurate setup in Parakh, and what was its overall pass rate?  
  → abstained:invalid_json (top sim 0.459) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'To_the_best_of_my_knowledge': "there isn't any specific information provided about the accurac
- `s800_o50_hybrid` **q04** Why does the Energy-Aware GPU project not trust the NVML hardware energy counter?  
  → abstained:llm_error (top sim 0.618) - ollama:qwen2.5:7b: Server error '500 Internal Server Error' for url 'http://localhost:11434/api/chat'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500
- `s800_o50_hybrid` **q05** In the measured scheduling run of the Energy-Aware GPU project, what window energy did the performance and energy-aware policies use?  
  → abstained:uncited_claim (top sim 0.744) - model answered but gave no claims
- `s800_o50_hybrid` **q06** According to the Energy-Aware GPU project, which knob is needed for energy-aware scheduling to beat race-to-idle?  
  → abstained:llm_error (top sim 0.686) - ollama:qwen2.5:7b: timed out
- `s800_o50_hybrid` **q07** What two fusion strategies does the investment scam detector offer?  
  → abstained:invalid_json (top sim 0.564) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'answer': 'The investment scam detector offers two fusion strategies: simple average and weight
- `s800_o50_hybrid` **q08** What ROC-AUC does the investment scam detector reach with the URL expert added?  
  → abstained:uncited_claim (top sim 0.495) - model answered but gave no claims
- `s800_o50_hybrid` **q09** In the investment scam detector, which classifier handles the image modality and what extracts the visual features?  
  → abstained:invalid_json (top sim 0.519) - JSON has the wrong shape: [{'type': 'bool_type', 'loc': ('abstained',), 'msg': 'Input should be a valid boolean', 'input': [], 'url': 'https://errors.pydantic.dev/2.14/v/bool_type'}]
- `s800_o50_hybrid` **q10** What risk levels can the Diabetes Insight Dashboard return?  
  → abstained:invalid_json (top sim 0.723) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'riskLevels': ['Low', 'Medium', 'High']}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}]
- `s800_o50_hybrid` **q11** Which backend framework and machine learning library does the Diabetes Insight Dashboard use?  
  → abstained:invalid_json (top sim 0.709) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'backend_framework': 'Flask', 'machine_learning_library': 'Scikit-learn'}, 'url': 'https://erro
- `s800_o50_hybrid` **q12** On which port does the Diabetes Insight Dashboard frontend dev server run?  
  → abstained:invalid_json (top sim 0.501) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'port': 3000}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}]
- `s800_o50_hybrid` **q13** How does the ReachInbox scheduler schedule emails without using cron?  
  → abstained:invalid_json (top sim 0.562) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'ReachInbox Scheduler': {'Key Features': ['Survives restarts: Redis AOF, deterministic job ids,
- `s800_o50_hybrid` **q14** What is the default minimum delay between two sends from the same sender in ReachInbox?  
  → abstained:uncited_claim (top sim 0.440) - model answered but gave no claims
- `s800_o50_hybrid` **q15** What happens to email search in ReachInbox when Elasticsearch is down?  
  → abstained:invalid_json (top sim 0.473) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'answer': 'When Elasticsearch is down in ReachInbox, the system falls back to using Postgres fo
- `s800_o50_hybrid` **q16** Under what circumstance can ReachInbox send the same email twice?  
  → abstained:uncited_claim (top sim 0.371) - model answered but gave no claims
- `s800_o50_hybrid` **q17** How does ShopZone stop stock from going negative when many buyers check out at once?  
  → abstained:llm_error (top sim 0.501) - ollama:qwen2.5:7b: Server error '500 Internal Server Error' for url 'http://localhost:11434/api/chat'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500
- `s800_o50_hybrid` **q18** How many API tests does ShopZone have, and how many of them fail on the original code?  
  → abstained:uncited_claim (top sim 0.496) - model answered but gave no claims
- `s800_o50_hybrid` **q19** Which external services does ShopZone use for geolocation and exchange rates?  
  → abstained:invalid_json (top sim 0.446) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'geolocation_service': 'MaxMind GeoIP2', 'exchange_rate_service': 'Open Exchange Rates API'}, '
- `s800_o50_hybrid` **q20** Which model architecture does the Underwater Microplastic Detection system use?  
  → abstained:uncited_claim (top sim 0.681) - model answered but gave no claims
- `s800_o50_hybrid` **q21** What validation accuracy does the underwater microplastic classifier report?  
  → abstained:invalid_json (top sim 0.672) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'validation accuracy': '0.96'}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}]
- `s800_o50_hybrid` **q22** Which microplastic class is mapped to the Critical pollution state?  
  → abstained:invalid_json (top sim 0.409) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}]
- `s800_o50_hybrid` **q23** What signals make up Watermark's composite score for a stock move?  
  → abstained:invalid_json (top sim 0.547) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {"Watermark's composite score for a stock move": ['Price change', 'Volume change', 'Volatility']
- `s800_o50_hybrid` **q24** In Watermark, what score opens an event and what score keeps an existing event alive?  
  → abstained:invalid_json (top sim 0.485) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'open_score': 2.0, 'keep_score': 1.0}, 'url': 'https://errors.pydantic.dev/2.14/v/missing'}]
- `s800_o50_hybrid` **q25** How much did Watermark's median digest latency drop after collapsing five queries into two?  
  → abstained:invalid_json (top sim 0.656) - JSON has the wrong shape: [{'type': 'missing', 'loc': ('abstained',), 'msg': 'Field required', 'input': {'answer': 'The median digest latency dropped from 1.2s to 0.1s after collapsing five queries in
