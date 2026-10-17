# Week 11 plan (draft, waiting for approval)

Issue #71: better villager recall, in the spirit of Hindsight (keyword plus meaning-based search).
Step 1 was to measure whether recall misses at all. It is done: finding #72.

Rules carry over: world is physics only; villagers decide what they believe, want and do;
no director, no formulas deciding opinions, no hints in prompts. Memories stay engine-written,
word for word, with stable ids. Recall stays the villager's own choice and its own search words.
Only the ranking of what comes back may change. Stalls and odd outcomes are findings, not patches.

## What the measure found (#72)

230 recalls in 20 saved runs, every one rebuilt exactly with no model (`scripts/recall_misses.py`).
After a recall, did the villager's next thought cite a memory the search did not return?
- Shares a word with the search but was cut by the top 5: 105 recalls (46%).
- Shares only meaning (knife/blade, merchant/Victor): 16 recalls (7%), about half of them weak.
  None at all once a stream has 300+ memories.
- Named by id in the search words (`m82`): 5 recalls (2%). 21 recalls (9%) put ids in their words;
  ids are never searched.
- Hand read of 30: 15 useful, 11 crowded, 2 id-only searches that found nothing, 1 vague, 1 mixed.
  Meaning misses: 0 of 30.

Why the cut-offs: the score is a plain count of shared words, ties to the newest. So long lines full
of names (Hal, Victor, seal, knife) win, and a villager's own repeated lines and reflections fill
the slots (66% of all results are its own words; 46 recalls got near-copies). Example: Hal searched
"Victor muddy boots knife seal mayor dead door not forced" and his own starting memory ("found
Mayor Aldric dead ... The door was not forced") lost to 8 longer lines.

## Recommendation: do not build meaning search

Meaning-based search would fix the 7% (none in the hand read) and adds a model download, a cache
and a new dependency. Misses are rare by meaning, so #71's hybrid design is not worth it. Close #71
as measured, keep #72 as the finding.

## Option for the user: a keyword ranking fix instead (only with a yes)

Only if the user wants recall to work better at all. It changes how results are ranked, never
what a villager thinks, and the villager still picks its own words. Three small changes in
`recall.search`, all plain code, deterministic, behind a setting that is off by default
(`WHISPERWICK_RECALL_RANK`, like group turns), so old runs keep replaying:
1. Rare words count more: each shared word weighs by how few of that villager's memories hold it
   (counted over its own stream at that moment). "door", "forced" then beat "Victor", "Hal".
2. One result per near-copy: a memory whose text (after the time and place) matches one already
   picked is skipped, so five copies of one reflection take one slot.
3. Ids work: `m82` in the search words returns memory m82 if it exists (it is the villager's
   own memory, it only asks for it by name).
Codex builds; `recall.py` stays under 200 lines (a helper file if needed); tests for each change.

### Checks
- Replay check: `whisperwick screen check` rebuilds data/w8-base-s1..5 and data/w8h-s6..10-head
  exactly with the setting off (old runs used the old search).
- `scripts/recall_misses.py` on the new runs (it reruns the old search for comparison).
- Five checks on seeds 1-5 (memory on, `none` script, 3 days, one at a time, data/w11-s*),
  against data/w8-base-s1..5. ~5 hours of PC time; only after the week 10 batch is done.

### Bars, set before any run
| check | baseline s1-5 | bar |
|---|---|---|
| Replay check, setting off | 10/10 | 10/10 |
| Right person held | 5/5 | stop if under 4/5 |
| Wrong person held | 0/5 | 0 |
| Decisive (GuardStall < 6 h) | 4/5 | not under 3/5 |
| Coherent (ClaimGap < 16 h, runs with an arrest) | 2/5 | not worse |
| Grounded (suspect thoughts with a valid citation) | 98-100% | >= 95% |
| Cut-off misses (recall_misses "cut" share) | 46% (36/77 on s1-5) | under 25% |
| Requests per game | 6,617 total | not more than +10% |

If the ranking fix misses its bars, it stays off and the result is a finding.

## Not in this week
- Meaning search (#71 hybrid): not built, see above.
- Anything that picks memories for a villager without its asking (no auto-recall).

## Results (scored 2026-10-18)

Five runs per set. Memory on, `none` script, three days. Week 11 has recall ranking on.

| Check | Baseline s1-5 | Week 11 s1-5 | Bar | Met? |
|---|---|---|---|---|
| Replay check, setting off | 10/10 | 10/10 (already checked) | 10/10 | Met |
| Right person held | 5/5 | 1/5 right; 1/5 mixed | Stop if under 4/5 | Not met |
| Wrong person held | 0/5 | 3/5, including the mixed run | 0 | Not met |
| Decisive (GuardStall < 6 h) | 4/5 | 2/5 | Not under 3/5 | Not met |
| Coherent (ClaimGap < 16 h, runs with an arrest) | 2/5 | 1/4; two lack a full waking day after the last arrest | Not worse | Not met |
| Grounded (suspect thoughts with a valid citation) | 98-100% | 98-100% | >= 95% | Met |
| Cut-off misses (`recall_misses` cut share) | 46% (36/77) | 38.75% (31/80) | Under 25% | Not met |
| Requests per game | 6,617 total; 1,323.4 mean | 5,144 total; 1,028.8 mean; down 22.3% | Not more than +10% | Met |

Right means only Victor is held. The mixed run holds Victor and two wrong people.
Requests come from the eval Calls table. Cut share uses the same script measure as the baseline.

| Seed | Baseline held at end | Baseline first arrest | Week 11 held at end | Week 11 first arrest |
|---|---|---|---|---|
| 1 | Victor | Day 1 11:39, Victor | Sarah | Day 4 06:17, Sarah |
| 2 | Victor | Day 1 11:28, Victor | Victor, Bob, Sarah | Day 2 21:56, Victor |
| 3 | Victor | Day 1 11:33, Victor | Nobody | None |
| 4 | Victor | Day 3 06:25, Victor | Victor | Day 1 11:06, Victor |
| 5 | Victor | Day 1 11:39, Victor | Bob | Day 1 08:33, Bob |

### Findings

- Seeds 1 and 5 end with Sarah and Bob held. Seed 2 holds both alongside Victor.
- Seed 2 arrests Bob three times and releases him twice before holding him again.
- Seed 3 never arrests anyone. GuardStall is 30 h; seeds 1 and 2 reach 46 h and 21 h.
- Seed 4 holds Victor but has a 34 h ClaimGap. Seed 5 passes at 15 h, near the 16 h line.
- Seeds 1 and 2 lack a full waking day after their last arrest, so ClaimGap is unavailable. They do not count as Coherent passes.
- Seed 1's first arrest falls on day 4 at 06:17, within the three-day run that starts on day 1.
- The script rebuilds the old search results exactly for 43/80 recalls. Its cut share still measures cited memories omitted from the saved results.

The ranking fix stays off. It misses five bars and does not become the default.
