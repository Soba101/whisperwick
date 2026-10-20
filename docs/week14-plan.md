# Week 14 plan (approved 2026-10-19): a different crime every game

Answers: keep the six villagers and shuffle roles; an accomplice in about 1 game in 4; the player is never the killer in v1.

Week 13 (roles and endings) is built and merged; its check runs are still going on the PC.
Rules carry over: the world is physics only; villagers decide what they believe, want and do;
no director, no formulas deciding opinions, no hints in prompts. Hal's arrests stay his own.
A generated crime is a set of **starting facts**, made by code from the seed before the game starts.
Nothing steers the story after that.

This updates #88 Q9 ("killer fixed to Victor for now"): from this week anyone can be the killer in play.
The original Victor scenario stays as the fixed benchmark for measured runs.

## Why this week
The playtests and the 2026-10-19 game show the same mystery wears thin fast: the same killer, the same
boots, the same lines. Donovan wants every game slightly different: any killer, any victim, sometimes
two people working together, different items. #100 also shows the story turns on whether news reaches
Hal, so different crimes should make different paths matter.

## What to build (Codex builds; I review and verify the engine)

### A. Crime generator (#103)
`whisperwick/crime/` builds a full Scenario from a seed, in code, from templates. No model.
- **Cast:** the six villagers we have (Alice, Bob, Sarah, Victor, Hal, the mayor) and their places stay;
  who is the victim, the killer and any accomplice is drawn. Hal (the authority) is never the killer
  or the victim in v1, so someone can still hold people. The player is never the killer in v1.
- **Crime:** victim, killer, an accomplice in about 1 game in 4, motive (debt, jealousy, a secret about
  to come out, an inheritance, revenge), weapon (an item that exists: knife, rope, candlestick,
  poison in a mug, ...), the place and the hour.
- **Clues, so every crime is solvable:** at least two independent true clues point at the killer
  (e.g. a weapon with a mark of the killer's trade, a stained item they still carry, a witness who saw
  them near the place at the hour), and one or two true-but-misleading facts about an innocent person.
  A small checker refuses any generated crime that breaks this, and the generator tries the next draw.
- **Starting memories:** built from the crime with fixed sentence templates: the killer remembers
  doing it (as Victor does now); an accomplice remembers their part and who they helped; witnesses
  remember only what they saw. Nobody is told what to do about it.
- **Items:** the weapon and clue items, plus a seeded mix of everyday goods per place (the goods scenario
  pool), consumables included (#99).
- **Same seed, same crime.** `whisperwick play --crime random` (play) or `--crime SEED` (replay a crime).
  The old scenario files still work exactly as before.

### B. Generated characters (#104, first half)
Per seed, from fixed pools: each villager's temperament, one grudge or debt with another villager,
one private wish (e.g. "wants to buy the inn"), and how they treat strangers. Written into the existing
`personality:` and `evidence:` lines as character and past facts, never as instructions about the crime
or what to believe. Innocent villagers then have their own reasons to hide things.

### C. Random seed in play, shown and shareable
The web start screen gets "Random crime" (default) and "Enter a seed". The seed is shown in the header
and on the ending screen ("Crime #83721"), so a game can be shared or replayed.

### D. A real ending scene
Replace the small text card with a full ending screen, on both pages:
- **What really happened:** a short account written by code from the crime and the log (no model):
  "Last night at 23:00 Bob killed Sarah in the Temple with the candlestick, over a debt. Alice helped
  him hide it." (templates only).
- **What Hal did:** each arrest and release on a small timeline, with his own words.
- **You:** your accusation (right or wrong), your side as plain facts, and who you talked to.
- **3D:** the camera glides to the Town Hall cell and the people Hal holds; the killer is marked.
- The crime number and "Play this crime again" / "New crime".

### E. More creative villagers: a measured screen (#104, second half)
No switch this week, only measurement:
1. Sampling temperature: the current setting vs one higher, on the fixed Victor scenario, seeds 1-2,
   5 runs each (the #90 run count). Watch Right person, Decisive, rejected actions, invented facts (#83).
2. One uncensored/abliterated model through the model screen (#67) on saved turns first; a live check
   only if its rejected-JSON rate is close to the current model's.
Donovan decides afterwards whether either one is adopted for play.

## Checks
- Engine verification (VERIFY.md) after A: determinism over generated crimes (same seed, same scenario,
  same events on the stub agent), and the old scenarios unchanged.
- Generator tests: 1,000 seeds produce valid scenarios; every crime passes the solvability checker;
  Hal is never killer or victim; accomplice rate near 1 in 4; no secret ever appears in a non-killer's
  memories.
- Live: 10 generated crimes, `none` player, 3 days: how often Hal holds the right person, compared with
  the Victor benchmark (#90). Reported, not judged: generated crimes are a different, harder test.
- Donovan plays 2-3 random crimes in 3D and says whether they felt different and fair.

## Open questions for you
1. Cast: keep our six villagers and shuffle the roles (my suggestion for v1), or also generate new names
   and jobs?
2. Accomplices: about 1 game in 4 (my suggestion), more, or less?
3. Should the player ever be the killer (a hidden role)? My suggestion: later, not v1.

## Not in this week
- Open world (#102, parked).
- Narrator (Q8, after this).
- Changing the measured benchmark: the Victor scenario stays fixed for comparisons.

## Results: E1, sampling temperature 1.0 (2026-10-20, #104)
10 runs (`none`, no role, memory on, 3 days), seeds 1-2 x 5, week 13 code plus LLM_TEMPERATURE only
(checkout ../whisperwick-w14e). Baseline: week 12 noise runs at 0.7 (w12n, 10 per seed). Data: data/w14t-*,
eval in data/w14t-eval-s1.txt and -s2.txt.

| Seed | Temperature | Right | Wrong | Nobody | Mixed | Decisive | Median requests | Invented-object lines per 1,000 talk |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.7 (10) | 2 | 1 | 5 | 2 | 3 | 1,313 | 2 |
| 1 | 1.0 (5) | 2 | 1 | 1 | 1 | 3 | 1,361 | 19 |
| 2 | 0.7 (10) | 9 | 1 | 0 | 0 | 8 | 1,638 | 3 |
| 2 | 1.0 (5) | 3 | 1 | 1 | 0 | 2 | 1,500 | 5 |

- Seed 2 got worse beyond noise: right person 90% to 60%, decisive 80% to 40%. Seed 1 about the same.
- Rejected actions did not rise (about 4-5% at both).
- Invented objects (#83: bag, book, clean boots, patrol logs, constable) are counted by word match in
  talk. At 1.0 one seed 1 run spiralled (75 lines); the rest are close to 0.7.
- Reading: a higher temperature does not make the game better on these measures and makes Hal less
  reliable on the easy seed. Recommendation: keep 0.7. "More creative" is better reached through the
  week 14 generated crimes and characters than through sampling.
