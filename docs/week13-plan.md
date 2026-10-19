# Week 13 plan (draft, for approval): roles and endings

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
  existing scripted players, 1 day, about 20 runs. Bars, from #90: Right person and Decisive not worse beyond
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
