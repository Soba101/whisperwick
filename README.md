# Whisperwick

A small village where every villager is an LLM agent.
Each villager believes its own version of events.
Only the world engine decides what is actually true.

> Status: **Week 3 — player + real objects.** Gate 1 passed. See [docs/week3-plan.md](docs/week3-plan.md).

## The question

Can a player's actions change an emergent story, while the story stays coherent
and every belief stays traceable to its source ("Alice thinks Bob did it, because Sarah told her")?

The long-term goal is a Skyrim-like world where agents keep the story moving and the player changes it.
This prototype builds the "brain" in text first. See [docs/roadmap.md](docs/roadmap.md).

## Core rule

- **Agents decide intentions. The world engine decides reality.**
- If something has a correct answer (who saw it, did the theft work), it lives in code.
- The LLM only decides what to say, and whether to lie.

## Quick start

```bash
uv sync                      # install dependencies
uv run whisperwick run       # run the default scenario for one game day
uv run pytest                # run every engine check (see VERIFY.md)
```

To use a real model, copy `.env.example` to `.env` and set the server and model first.

```bash
uv run whisperwick run --agent llm --days 3   # 3 game days with the model, saved to data/
uv run whisperwick story data/run-<name>.db   # read the run as a transcript (no model)
```

## Play

```bash
uv run whisperwick play --days 1                          # you play Wren in the terminal
uv run whisperwick play --script players/blame_hal.yaml   # a scripted player
```

Both need a model server (see `.env.example`). Type `help` in the game for commands.

After each run every villager is interviewed (who killed the mayor?), saved in the sidecar JSON.
Compare runs side by side (suspects, where items ended up, key events), no model needed:

```bash
uv run whisperwick compare data/run-a.db data/run-b.db
```

Trace a rumour: who suspects Hal, and the chain behind each belief (who told whom, back to
something seen first-hand or a lie with no source). Reads the belief log, no model;
add `--json` for the same thing as data. Older runs without a belief log print a short message:

```bash
uv run whisperwick trace data/run-a.db npc_hal
```

## How an agent acts

Agents never touch the world directly. They send an intent, and the engine decides:

```python
world.act({"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": "Morning."})
# -> ActionResult(ok=True, event=...)    or    ActionResult(ok=False, reason="npc_victor is not here")
```

Actions so far: `move`, `talk`, `look`, `take`, `drop`, `give`, `show`.

## Layout

```
whisperwick/     the engine (clock, events, actions, world, stub agent, CLI)
scenarios/       YAML scenarios, e.g. Murder of the Mayor
tests/           pytest tests
docs/            design notes and the proposal
data/            local SQLite event logs (git-ignored)
```

## Roadmap (6 weeks)

| Week | Focus | Exit check |
|---|---|---|
| 1 | Engine skeleton | A seeded run replays identically, no LLM |
| 2 | Vertical slice (local ~30B model) | **Gate 1:** a readable murder story from 5 NPCs |
| 3 | Player + real objects | Same seed, 3 player scripts, 3 different outcomes |
| 4 | Beliefs and rumours | A player's lie can be traced: who believes it, and via whom |
| 5 | Consequences + endings | Story ends in an engine-decided outcome |
| 6 | Evaluate + playable demo | **Gate 2:** GO / PIVOT / STOP |

Everything runs locally (Ollama on an RTX 5090). No paid APIs.

## License

MIT
