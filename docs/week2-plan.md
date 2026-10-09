# Week 2 plan: vertical slice -> Gate 1

Goal: a readable murder story from 5 NPCs, driven by a local model.
Model: Ollama `qwen3.8:27b` on the PC, OpenAI-style base URL in `.env`.
Each step is tracked as a GitHub issue under the "Week 2 - Gate 1" milestone.

## Steps

1. **LLM agent** (`settings.py`, `llm_client.py`, `llm_agent.py`)
   - `.env` holds `LLM_BASE_URL` and `LLM_MODEL`. The stub agent stays the default.
   - Call Ollama `/api/chat` with `format` = JSON schema, `think: false`, `keep_alive: "30m"`.
   - Build the schema per turn: `target` may only be an exit or a person here.
     So the model cannot write "Victor" instead of `npc_victor`.
   - Prompt: who you are, where you are, people and exits (with IDs), top memories.
   - A rejected intent gets one retry with the engine's reason, then falls back to `look`.
   - Tests use a fake client. No network in tests.
2. **Memory stream** (`memory.py`)
   - Each NPC remembers the events it witnessed (the engine already records witnesses).
   - Importance is scored in code by event type. No LLM call.
   - Retrieval = recency + importance + keyword relevance. Embeddings later if needed.
   - Reflection: one LLM call per NPC at the end of each game day.
   - Memory lives on the agent side, outside the world hash.
3. **Scheduler** (`scheduler.py`)
   - Wake an NPC when someone talks to it or arrives where it is, plus a 60-minute routine check.
   - Sleep 22:00-06:00 is handled in code (no LLM call).
4. **Murder setup** (scenario + small engine change)
   - Add `npc_mayor` to the YAML, dead in the Town Hall. Dead NPCs cannot act.
   - New `evidence:` block: private starting memories per NPC.
   - Only Victor's prompt knows he is guilty. Everyone else learns through events.
   - The golden snapshot will change on purpose.
5. **Run and read** (CLI)
   - `whisperwick run --agent llm --days 3` writes the SQLite event log.
   - `whisperwick story` prints a day-by-day transcript from the log (code, no LLM).
6. **Checks**
   - Engine checks stay on the stub agent.
   - Opt-in integration test, skipped unless `LLM_BASE_URL` is set.

## Gate 1 bar

- 3 game days run with no crashes.
- Under 5% of intents are rejected.
- NPCs discuss the death and use their own evidence.
- At least one accusation or argument happens.
- A human can read the story and follow it.

Rough cost: about 500-800 model calls per 3-day run, under 1 s each (about 15 minutes).
