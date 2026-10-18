# Week 12 plan (approved 2026-10-18: A and B; B items specific to each place)

Gate 2: GO, provisional (#87). Keep developing until the user calls a pivot.
Rules carry over: the world is physics only; villagers decide what they believe, want and do;
no director, no formulas deciding opinions, no hints in prompts. Stalls and odd outcomes are findings.

## Why this week
Two things block progress:
1. **Noise.** Two runs of the same seed end differently on 3 of 5 seeds (#80). Every five-run check
   (week 10, the week 11 drop in #86) cannot separate a real change from luck.
2. **The player has nothing to do.** The playtest (#74-#78) and week 10 show a player can't
   change the story much: the world has two items, and talk changes nothing.

## Options (pick one or two)

### A. Measure the noise (no code; PC time only)
Run the current main (`none` script, memory on, 3 days) 10 times each on seeds 1-2, one at a time.
That's about 20 x 35 min, roughly 12 h. Report how often the ending matches, and the spread of
GuardStall, ClaimGap and requests. Output: for each measure, how many runs it takes to trust a change.
Then rerun the week 11 ranking on the same 2 seeds x 10 to see whether #86 is real or noise.
Bar, set now: for each measure, the run count at which two batches of the same code agree.

### B. Everyday objects (physics; Codex builds)
Add plain objects to the scenario: coffee, bread and a mug at the Inn, coins for everyone, a ledger
at the Market, a candle at the Temple. They're things to take, give and show, with no rules about
what they mean. Then "here's your coffee" can be a real give (#74), and the player has more to do.
The scenario YAML plus validation tests; the engine already handles items. Check: 5 runs, the bars
from week 7 (Right person, Decisive, Grounded) not worse, plus a count of talk lines claiming
give/take with no matching event (#74, #84).

### C. A shorter talk limit (code, physics-like)
The feed is too long (#78: "too much text"). Today the engine rejects talk over 500 characters
(MAX_MESSAGE_CHARS, actions.py:17). Lower it (e.g. to 250) and keep everything else the same. Check: the same 5-run bars, and the playtest
feel. This changes what villagers can say, so it's the user's call.

### D. Play it yourself (Gate 2 questions)
Play one full game in the demo with the new hook line and answer the six questions in the week 10
plan, section 4. No code. It's the best input for picking the next feature.

## Recommendation
A first, run overnight on the PC: without it no result is trustworthy. B during the day, built by
Codex while A runs. Then check B with the run count A gives. D whenever you have 30 minutes.

## Not in this week
- Attack actions and the goal wording (#79, waiting on the user).
- Any change to what villagers are told or prompted.

## Results: A (noise), 2026-10-18
20 runs, current main (`none`, memory on, 3 days), seeds 1-2 x 10, only model sampling differs.
Data: data/w12n-*, eval output data/w12n-eval-s1.txt and -s2.txt.

| Seed | Right | Wrong | Mixed | Nobody | Pairs ending the same |
|---|---:|---:|---:|---:|---:|
| 1 | 2 | 1 | 2 | 5 | 12/45 |
| 2 | 9 | 1 | 0 | 0 | 36/45 |

| Measure | Seed 1 median (min-max) | Seed 2 median (min-max) |
|---|---|---|
| Requests | 1,314 (488-2,552) | 1,638 (1,049-3,019) |
| GuardStall h | 31 (1.3-48) | 3.4 (1-7.2) |
| ClaimGap h | 19 (17-25), not reached in 7/10 | 18 (10-31) |
| Rejected % | 3.7 (1.1-5.8) | 4.8 (2.4-9.7) |

**The seed matters more than the luck.** Seed 2 is easy (9/10 right, Hal acts on day 1); seed 1 is hard
(2/10 right, Hal holds no one in 5/10). A batch that mixes seeds mostly measures which seeds it used.

**Runs needed** (two disjoint batches of the same code giving the same pass/fail verdict 80% of the time,
by resampling the 10 repeats):

| Measure | Seed 1 | Seed 2 | Verdict |
|---|---|---|---|
| Right person (bar 80%) | 3 | 5 | 5 runs per seed is enough |
| Decisive (GuardStall < 6 h, bar 60%) | 4 | 3 | 5 runs per seed is enough |
| Coherent (ClaimGap < 16 h, bar 40%) | 3 | more than 5 | not trustworthy at 5 |
| Requests within 10% | more than 5 | more than 5 | not trustworthy even at 10 |

Bar (set in the plan): met for Right person and Decisive; not met for Coherent and Requests.

**Week 11 (#86).** Right person fell from 5/5 to 1/5. On one seed, two 5-run batches of the same code
differ by at most 40 points (seed 1) or 20 (seed 2); week 11's drop was 80. So the drop is probably real,
not noise, but #86 used five different seeds, so this is a strong hint, not proof. The ranking fix stays off.
The planned rerun of the ranking on seeds 1-2 x 10 would settle it (about 12 h of PC time).

**Not measurable.** Rejections are counted but not logged as events (#45), so how many are "not reachable"
moves (#73) can't be recovered: 1,356 rejections in 31,708 requests.

**What changes.** From now on a check runs 5 repeats each on fixed seeds (1 and 2 at least), compares the
same seeds before and after, and treats ClaimGap and Requests as rough until 10+ runs.
