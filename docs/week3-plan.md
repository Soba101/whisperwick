# Week 3 plan: player + real objects

Goal: the player is in the world, real objects exist, and the player's actions change the story.
Exit check: same seed, 3 player scripts, 3 different outcomes.
Issues: #15 player, #16 objects, #17 play mode, #18 scripts + report.

## Design in one paragraph

The player is just another actor (id `player`), so the engine needs no special case:
the player's intents go through `World.act()` like everyone else's, and NPCs see, hear and remember the player.
Objects are engine facts with exactly one place: on the ground at a location, or held by someone.
Four verbs move them: `take`, `drop`, `give`, `show`. Every one is a logged event with witnesses.
The LLM never says where an object is; the engine does.

## Tasks (in order)

### 1. Objects in the engine (#16)
- `Item` model: `id`, `name`, `description`, and either `location` or `holder` (never both).
- Verbs (new handlers in `actions.py`, each rejects with a reason):
  - `take item` — item is on the ground here.
  - `drop item` — you hold it; it lands here. (Needed to hide something.)
  - `give item` to a person here — you hold it; they now hold it.
  - `show item` to a person here — you hold it; nothing moves, but everyone here witnesses it.
- `Intent` gets one new field: `item`.
- `look` lists items on the ground here. Held items stay private until shown or given.
- World save/load and state hash include items. New invariant: every item is in exactly one valid place, and a holder is alive.
- Scenario: the bloody knife lies in the Town Hall by the body; Victor holds his muddy boots.
- Tests: legality of each verb, determinism and save/load with items, invariant.
- The snapshot changes on purpose (items are now in the state).

### 2. Player actor (#15)
- Scenario gets a `player` entry (a newcomer at the market). It is an NPC record with id `player`.
- The LLM scheduler never schedules `player`, and the player gets no memory stream or reflection.
- NPC prompts show the player like any other person, so NPCs can talk to them.
- Tests: player intents are accepted and rejected like NPC intents; NPCs witness them; the scheduler skips the player.

### 3. NPCs use objects + memories and story (#16, LLM side)
- LLM schema and prompt: the four new actions, with `item` limited to real ids (items here or held).
- Memory and story text for the new events, e.g. "the newcomer showed Bob a bloody knife".
- Tests with a fake model client, no live calls.

### 4. `whisperwick play` (#17)
- Script mode: `whisperwick play --script players/x.yaml --days 3 --db data/X.db`.
  The script is a list of timed intents, e.g. `{at: "1 09:00", action: talk, target: npc_bob, message: "..."}`.
  At that minute the player's intent runs first, then the NPCs. A rejected step is printed and logged, not fatal.
- Terminal mode: `whisperwick play --days 3` with no script. Each turn shows what the player sees,
  then reads one command: `move loc_inn`, `talk npc_bob Hello`, `take item_knife`, `wait 30`, `quit`.
  `wait N` lets the village run N minutes.
- Both modes use the same loop; only the source of player intents differs.
- Tests: script loading, a scripted run with a fake client, command parsing.

### 5. Three scripts + divergence report (#18)
- `players/none.yaml` (does nothing), `players/blame_hal.yaml` (tells Bob "Hal did it"),
  `players/hide_knife.yaml` (takes the knife and drops it at the Temple).
- End-of-run interview: after day 3, each NPC gets one read-only question,
  "Who killed the mayor?" → `{suspect, why}`. Saved in the run's sidecar file, never in the event log.
- `whisperwick compare a.db b.db c.db`: per run, each NPC's suspect, where the knife ended up,
  and the key player/object events. Plain text.
- Live: 3 runs on the Mac (model on the PC), ~10 min each. Plus a second "none" run to measure run-to-run noise,
  so we only count differences bigger than the noise.

## Who does what
- Sonnet subagents implement tasks 1-5 and write the tests.
- I review every diff, run `uv run pytest` + `ruff` and the verify-world-engine check after engine changes, then commit on the Mac.
- Order: 1 → 2 and 3 in parallel → 4 → 5 → live runs. Findings become GitHub issues.

## Out of scope (later weeks)
- Beliefs with sources and trust in the player (week 4). The interview is a stand-in until then.
- Accuse / arrest and endings (week 5).

## Risks
- **Model noise hides the player's effect.** The second "none" run measures it.
- **Hal sees the player take the knife** (he starts in the Town Hall). That is fine: it is a real consequence, and the report will show it.
- **More actions = more rejected intents.** Watch the rejection rate; it was 0.7% in run 2.
