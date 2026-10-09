# Week 4 plan: beliefs, rumours and trust

Goal: every villager holds beliefs with a source, rumours spread through talk,
and trust in the teller decides how much a rumour counts (the player included).
Exit check: **a player's lie can be traced: who believes it, and via whom.**
Fixes #11 (invented facts) and #12 (talk and show loops). Covers #23 (killer gives away evidence).

## Design in one paragraph

A claim is structured, not free text: `{kind: killer | innocent, subject: <person id>}`.
A `talk` may carry one claim next to its message. The engine checks only that it is well formed
(it does not check if it is true: lies are allowed) and logs it in the talk event, with witnesses.
Beliefs live on the agent side, like memories, and never touch `state_hash`.
They are a pure function of the event log plus the scenario: same events in, same beliefs out.
So the code, not the model, decides where every belief came from, and a run's beliefs
can be rebuilt and traced from its `.db` file with no model.
Free text can still invent things (a ledger), but **only structured claims change beliefs**,
so an invented fact can no longer spread as a belief (#11).

## The rules (all in code, all deterministic)

- A belief is "X killed the mayor", with a confidence (0..1) and a list of sources.
- A source is one of: `saw` (starting evidence, or witnessing a telling item being shown),
  `told` (by person P, in event E), `own` (said with no backing: a guess or a lie).
- Hearing `killer X` from P: confidence rises by `trust[P] x 0.5 x (1 - confidence)`.
  Hearing `innocent X`: confidence falls by `trust[P] x 0.5` of itself.
- Items get a `points_to` field (knife and boots point to Victor). Seeing one shown or given
  adds a `saw` source pointing at that person (+0.3 of the gap).
- Trust starts at 0.5 between villagers and **0.3 towards the player** (a stranger).
  If P's claim goes against something I saw myself, my trust in P drops 0.15.
  If it agrees, it rises 0.05. Clamped to 0..1.
- When P makes a claim, its source is P's own matching belief if P has one; otherwise `own`.
  This is what makes the chain: Victor ← Bob (event 88) ← Wren (event 12, `own` = the lie).
- Scenario adds starting beliefs and confidences (Bob and Alice lean Victor from what they saw),
  and per-NPC goals. Victor's goal: avoid suspicion.

## Tasks (in order)

### 1. Claims in the engine
- `Intent.claim` (optional, talk only). Rejected with a reason if the kind is unknown,
  the subject is not a real person, or the action is not `talk`.
- The talk event's `data` holds the claim. Memory and story text show it.
- Player script steps and the terminal get a claim: `claim: {kind: killer, subject: npc_hal}`
  and `tell npc_bob killer npc_hal <message>`. `players/blame_hal.yaml` uses it.
- Tests: legality, logging, determinism. The stub never makes claims, so the snapshot should not change.
- Run verify-world-engine.

### 2. Beliefs and trust (`beliefs.py`, `trust.py`)
- `Beliefs.update(event)` applies the rules above. `replay(events, scenario)` rebuilds them from a log.
- Scenario: `beliefs`, `trust` defaults, `goals`, item `points_to`.
- Tests: each rule, the player's lower trust, a three-hop chain, replay equals live.

### 3. LLM side + loops (#12, #23)
- Prompt shows: my goal, what I believe and why ("Victor, 70%: saw his boots, told by Bob"),
  who I trust, and my last 3 lines to the person in front of me.
- Schema gets `claim`, with `subject` limited to real person ids.
- Items in the prompt are marked when they point at me ("this points to you").
- Repeat guard (agent side, before `World.act`): the same show, give or claim to the same person
  within 2 game hours is rejected with a reason ("you already showed Bob the knife at 09:12"),
  and counts as a rejection.
- Tests with a fake model client.

### 4. Trace + report
- Sidecar JSON saves each NPC's final beliefs, trust and sources.
- Interview: add the code answer (top belief, killer excluded) next to the model's answer.
- `whisperwick trace data/X.db npc_hal`: who believes "Hal did it", how much, and the chain
  of tellers back to the origin, with event ids and times. Rebuilt from the log, no model.
- `compare` gets belief columns and the player's trust at the end.

### 5. Live runs
- Short 1-day smoke run, then none, blame_hal (with claims), hide_knife: 3 days each, seed 42.
- Results on the week 4 report issue. Measure: the blame_hal trace, % of claims with
  a source vs `own`, repeated shows (target 0), Victor showing or giving the boots or knife (target 0).

## Who does what
- Sonnet subagents implement tasks 1-4 and write the tests. I review every diff,
  run `uv run pytest` + `ruff`, and verify-world-engine after task 1. Commits on the Mac.
- Order: 1 → 2 → 3 and 4 in parallel → 5. One issue per task on the board; findings become issues.

## Out of scope
- Accuse and arrest, endings (week 5, #24). Parallel NPC calls (#20, week 6).
- Beliefs about anything but the murder. Beliefs formed by the model's own reasoning
  (they are not in the log, so they could not be traced).

## Risks
- **The model rarely attaches claims.** Then rumours stay in free text and do not spread.
  Watch the claim rate in the smoke run; tighten the prompt if it is low.
- **The numbers are made up.** 0.5 / 0.3 / 0.15 are starting guesses, kept as named constants.
- **Victor may still play against himself.** The goal and the "points to you" mark are a prompt fix;
  the run measures whether it holds.
