# Notes for coding agents (and future me)

## The one rule
Agents decide intentions. The world engine decides reality.
- An LLM never writes world state directly.
- It returns a structured intent (JSON). The engine validates it, resolves it, and logs an event.
- If something has a correct answer, it belongs in code, not in a prompt.

## Code style
- Simple, small, modular. Keep files under ~200 lines.
- Lots of comments, in short plain sentences. Explain *why*, not just *what*.
- Never delete old comments unless they are clearly wrong.
- Every object has a stable ID (`npc_alice`, `loc_inn`). Never look things up by display name.
- Same seed in, same events out. No unseeded randomness anywhere in the engine.

## Before you say "done"
- `uv run pytest` passes.
- `uv run ruff check .` is clean.

## Design docs
- `docs/proposal.md`: the plan, decisions and roadmap.
