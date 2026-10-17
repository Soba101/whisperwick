# Week 12 plan (draft, waiting for approval)

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
