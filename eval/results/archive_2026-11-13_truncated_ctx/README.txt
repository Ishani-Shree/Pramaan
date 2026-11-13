Run with Ollama's default 2,048-token context window.
Prompts for 800-word chunks (~4.6k-7.2k tokens) were silently truncated by Ollama
(server.log: 114x 'truncating input prompt limit=2050'), so the s800 results here are invalid.
Kept as a record of the bug; fixed by setting num_ctx=16384 in app/llm.py.
