# Whisperwick

A small village where every villager is an LLM agent.
Each villager believes its own version of events.
Only the world engine decides what is actually true.

> Status: **Week 1 — engine skeleton.** No LLM yet. Villagers can move, talk and look.

## The question

Do beliefs with tracked sources ("Alice thinks Bob did it, because Sarah told her"),
inside an authoritative world engine, produce emergent stories that are more coherent
than the [Generative Agents](https://arxiv.org/abs/2304.03442) baseline?

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

## How an agent acts

Agents never touch the world directly. They send an intent, and the engine decides:

```python
world.act({"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": "Morning."})
# -> ActionResult(ok=True, event=...)    or    ActionResult(ok=False, reason="npc_victor is not here")
```

Actions so far: `move`, `talk`, `look`.

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
| 3 | Beliefs and rumours | Two NPCs hold conflicting, traceable beliefs |
| 4 | Scale + evaluation harness | 20 NPCs, 5 seeds x 4 conditions, unattended |
| 5 | Cheap model tier | Quality drop of an 8B model measured |
| 6 | Evaluate and write up | **Gate 2:** GO / PIVOT / STOP |

Everything runs locally (vLLM on an RTX 5090). No paid APIs.

## License

MIT
