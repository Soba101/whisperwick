# Whisperwick

A small village where every villager is an LLM agent.
Each villager believes its own version of events.
Only the world engine decides what is actually true.

> Status: **Week 9 done, week 10 in progress.** Weeks 1-6 built the engine, the player, cited beliefs,
> arrests and endings, and a playable demo (`whisperwick play --web`, `whisperwick replay`).
> Weeks 7-9 measured why villagers fail, kept the evidence heading, and tried every speed idea
> (a 3-day game still takes 45-75 minutes). Week 10 measures the player's effect, then Gate 2.
> See [docs/week10-plan.md](docs/week10-plan.md).

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
uv run whisperwick play --web                             # play in a web page (notes, what you know)
```

Both need a model server (see `.env.example`). Type `help` in the game for commands.

The 2D page first asks you to choose the mayor's cousin (`cousin`), a travelling peddler
(`peddler`), Victor's old business partner (`partner`), or the original newcomer start.
Each role has starting items and one private fact under **What you know**. The cousin
and partner also have one villager who already knows them. Villagers decide how to respond.
`--role` preselects a role in the web picker and selects it directly for terminal or script play:

```bash
uv run whisperwick play --role cousin --seed 1
uv run whisperwick play --role peddler --seed 1
uv run whisperwick play --role partner --seed 1
uv run whisperwick play --web --role partner --seed 1
uv run whisperwick play --role peddler --script players/none.yaml --days 3 --seed 1
```

Web play defaults to one village day. Explicit `--days` values are preserved, including
three-day scripted measurements. Omitting `--role` keeps the original world start.
At the end of a web game, privately name someone or nobody to reveal the ending.
The accusation is saved in the run's JSON sidecar; villagers never see it.
The report gives the truth, Hal's custody and arrest times, your accusation, and counted
gives and shows to Victor. Read the same report later without calling a model:

```bash
uv run whisperwick outcome data/web-YYYYMMDD-HHMMSS-1.db
```

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

Measure runs (`eval`), judge them (`judge`), or screen a new model against saved turns in minutes
before any full run (`screen`, see issue #67):

```bash
uv run whisperwick eval data/run-a.db data/run-b.db
uv run whisperwick screen run data/screen/qwen-turns.json --out data/screen/new-model.json
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

## Roadmap

| Week | Focus | Exit check |
|---|---|---|
| 1 | Engine skeleton | A seeded run replays identically, no LLM |
| 2 | Vertical slice (local ~30B model) | **Gate 1:** a readable murder story from 5 NPCs |
| 3 | Player + real objects | Same seed, 3 player scripts, 3 different outcomes |
| 4 | Beliefs and rumours | A player's lie can be traced: who believes it, and via whom |
| 5 | Consequences + endings | Story ends in an engine-decided outcome |
| 6 | Evaluate + playable demo | Done: villager memory, evaluation runs, terminal and web demo |
| 7 | Why villagers fail | Done: five checks measured (#61, #62) |
| 8 | Behaviour + speed | Done: evidence heading kept (right person 8/10); speed items dropped |
| 9 | Model screen + group turns | Done: screen works (#67); group turns and vLLM not kept (#68, #64) |
| 10 | Player effect + Gate 2 | In progress: [week10-plan.md](docs/week10-plan.md) |
| 11 | Recall search | Next: measure recall misses first (#71) |
| later | **Gate 2** | GO (front-end) / PIVOT / STOP, once the villagers work |

Everything runs locally (a local model on an RTX 5090, served by llama-server). No paid APIs.

## License

MIT
