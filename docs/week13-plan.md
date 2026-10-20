# Week 13 plan (approved 2026-10-19): roles and endings

Answers: side = plain facts; 1 day for play, 3 days for measured runs; role choice in the 2D page first.

Gate 2: GO, provisional (#87). Direction draft: #88 (answers Q1-Q12). Build order (Q12): roles and endings
first, the engine-written narrator after (week 14 candidate).
Rules carry over: the world is physics only; villagers decide what they believe, want and do;
no director, no formulas deciding opinions, no hints in prompts. Hal's arrest stays his own choice.
Stalls and odd outcomes are findings. The player side may be "gamey" (#88 Q3); the villager side may not.

## Why this week
The playtest and week 10 show the player has no reason to be in the story (#74-#78, #80-#84).
#88 settled what the game is: a newcomer with a chosen role, one day, a clear goal you may ignore,
and an ending that tells you what really happened.

## What to build (Codex builds; I review)

### 1. Roles (player only, chosen at the start)
A role is a small scenario overlay, in YAML next to the scenario (`scenarios/roles/*.yaml`), applied by code
before the world is built. It may set only starting facts, the same kinds the scenario already has:
- **name and occupation** of the player record (today: Wren, newcomer);
- **starting items** (as in the goods scenario, merged in #95);
- **who already knows you**: one starting memory line for that villager, like the `evidence:` lines today
  (e.g. Alice: "My cousin Wren, Mayor Aldric's cousin, arrived in the village yesterday.");
- **one private fact** for the player, drawn at random per game with the run seed from a pool of true facts
  (see 2).

Three roles from #88:
| Role | Items | Knows you | Notes |
|---|---|---|---|
| The mayor's cousin | a letter from the mayor (an item) | Alice | personal stake |
| Travelling peddler | extra goods and coins (goods scenario items) | nobody | the control role: no villager change |
| Victor's old business partner | a ledger page (an item) | Victor | the "team up with the killer" role (Q9); Victor decides whether to trust you |

No role adds a rule, a mechanic or a hint for any villager. A role's "knows you" line is a fact about the past,
nothing about the murder.

### 2. The private fact pool
A list in the scenario: `facts:`, true statements a newcomer could plausibly have learned, each one already true
in the world (an item's place, a villager's trade, an `evidence` line seen from outside). Never the answer itself:
Victor's confession and `secrets:` are never in the pool. The draw is seeded, so the same seed gives the same fact.
The player sees it under "What you know"; no villager is told anything.

### 3. One-day game and a hook
`--days 1` for player games (15-30 min, Q4). The hook line from #75 stays. The goal shown to the player:
"Find out who killed Mayor Aldric before nightfall, or don't: it's your day." (Q1; player-side text only.)

### 4. The accusation
At the end of the day the player names one person (or nobody) on a final screen. It's a player-side record,
not a world action: villagers never see it and it changes nothing in the world. Hal's arrests stay his own.

### 5. The ending report
Code builds it from the log and `secrets:` (no model):
- **The truth:** who did it.
- **What Hal did:** who he holds at the end, and when he made each arrest.
- **Your accusation:** right or wrong.
- **Your side:** **open question for you**. My suggestion: say it plainly from facts, not a score.
  For example: "You accused Victor." / "You named Bob; Hal holds Bob; Victor walks free." Plus whether you
  gave Victor anything or warned him, as counted events. No "good/evil" label.
Shown in the 2D page and the 3D page (#96), and printed by `whisperwick outcome`.

## Checks
- Unit tests: role overlays only add the allowed kinds; the fact pool never contains the secret or Victor's line;
  the same seed draws the same fact; the report matches hand-built logs.
- Villagers unchanged without a player: the `none` script with no role must give the same events as main
  (determinism test on a stub agent).
- Live: the peddler (no villager change) and the partner (Victor knows you), 5 runs each on seeds 1-2 with the
  existing scripted players, 3 days (measured runs keep 3 days), about 20 runs. Bars, from #90: Right person and Decisive not worse beyond
  noise against 5 fresh runs per seed without a role. ClaimGap and Requests reported, not judged.
- You play each role once in the demo and say whether the ending felt fair.

## Open questions for you
1. "Your side" wording: plain facts (my suggestion) or a named verdict?
2. Is one day right for the first build, or keep 3 days for the measured runs and 1 day only for play?
3. Should the role choice also live in the 3D page this week, or 2D only until #96 is merged?

## Not in this week
- The narrator (week 14 candidate).
- Dice (Q7, later).
- Attacks (#79, still open).
- Route-finding (#73), seen/told tags (#93), recall by links (#94).

## Implementation notes (2026-10-19)

Built the approved roles and fact pools, role selection for terminal/scripts and the
2D start page, private starting knowledge, a private final accusation, and a code-written
ending in the 2D page and `whisperwick outcome`. Villager prompt templates, personality,
authority rules and engine actions are unchanged. Role YAML rejects fields outside the
allowed starting facts. Facts use a separate RNG seeded with the run seed.

No-role event parity is checked against SHA-256 digests captured from main commit
`5783dce48ca16fe76407c7eaba56c4b9a1804b49`: both scenarios, seeds 1 and 42, 300 stub ticks
with the `none` player. The fixture lives in `tests/fixtures/week13_main_events.json`.

Try `uv run whisperwick play --web` to choose a role before any world starts.
For terminal play, use `--role cousin`, `--role peddler`, or `--role partner`.
Keep `--days 3` on measured scripts. Usage examples are in the README.

Validation: Ruff clean; 670 tests passed and one live-model test skipped. Eleven HTTP
socket tests cannot bind localhost in the sandbox. Routes and inline controls also have
socket-free tests. Live model comparisons and human playthroughs of each role remain
unrun; the provisional gate has not been re-evaluated from new live measurements.

Review fixes: role YAML now separates public `occupation` from player-only `title`.
The title stays on the scenario, outside world NPC records, and appears in the player's
web panel, terminal introduction and ending. Prompt regression tests cover all three
roles, including the peddler's visible trade and the one villager's authored memory.
Endings use scenario authority IDs and the saved murderer ID; sidecars retain authority
and player title so the ending still works when the scenario file is unavailable.

## Results: check runs, 2026-10-20 (#97)
20 runs (`none` script, memory on, 3 days), roles peddler and partner x seeds 1-2 x 5. Baseline: the week 12
noise runs (w12n, 10 per seed, no role, week 12 code). Data: data/w13r-*, eval in data/w13r-eval-*.txt and
data/w13r-base-s*.txt.

| Seed | Group | Right | Wrong | Nobody | Mixed | Decisive (GuardStall < 6 h) | Median requests |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | no role (10) | 2 | 1 | 5 | 2 | 3 | 1,313 |
| 1 | peddler (5) | 4 | 0 | 1 | 0 | 4 | 1,048 |
| 1 | partner (5) | 2 | 0 | 3 | 0 | 1 | 902 |
| 2 | no role (10) | 9 | 1 | 0 | 0 | 8 | 1,638 |
| 2 | peddler (5) | 2 | 1 | 1 | 1 | 2 | 1,432 |
| 2 | partner (5) | 3 | 0 | 2 | 0 | 3 | 2,019 |

- Pooled over both seeds nothing moved: right person 55% without a role, 60% peddler, 50% partner.
- Per seed it did: seed 1 got better with the peddler (80% vs 20%), seed 2 got worse with both roles
  (40% and 60% vs 90%). Seed 2's drop is past the noise found in #90 (20 points for 5-run batches).
- So the bar (Right person and Decisive not worse beyond noise) is **not met on seed 2**.
- The baseline is fair: between the week 12 runs and these, the only villager-side change is the role
  overlay (scenario.py, roles.py, the facts pool), and with no role the events match main (stub test).
  So the swings come from the role itself: the peddler changes the player's public occupation and
  starting items; the partner also gives Victor a memory of the player.
- Reading: a small change to who the player is pushes a seed either way (seed 1 up, seed 2 down).
  That makes the game less predictable per seed, which is fine for play, but it means a role's effect
  can only be judged over many seeds, not two. Finding #119.
