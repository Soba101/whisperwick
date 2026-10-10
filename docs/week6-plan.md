# Week 6 plan: villager memory, evaluation and Gate 2

Goal: answer the roadmap question with evidence. Can a player's actions change an emergent story,
while the story stays coherent and every belief stays traceable?
Then decide Gate 2: GO (front-end) / PIVOT / STOP.

What week 5 showed (seed 42, 4 runs, #41):
- Hal arrested Bob (innocent) in every run, for "obstruction"; Victor (the killer) stayed free; no releases.
  The player's actions did not change the ending, even "Victor did it" told straight to Hal (#48).
- Hal misread a look memory and came to believe Bob was dead (#49). Arrests carry no reason (#50).
- The unverified-tag name check flags 8-26% of claims (#51). Aims are mostly restated as "new" (#52).
- Good news: 0 model errors, 1.6-2.9% rejections, every arrest traces back to Hal's own thinking.
So week 6 must first find out if "Hal arrests Bob" is this seed and these two characters, or the setup itself.

Exit check: **a results table over several seeds and player scripts, with outcome divergence,
coherence, % of beliefs with a valid source and the memory-slip rate, and a Gate 2 decision.**

Rules carry over: the world is physics only; villagers decide what they believe, want and do;
no director, no formulas, no hints in prompts. Every new piece is agent-side and private, never world state.

## 1. Faster runs (#20), changed after measuring (2026-10-11)
- Measured first: in the week 5 logs, minutes where 2+ villagers act are almost all one
  conversation in one place. Each reply must see the line before it, so those calls cannot overlap.
  Parallel acting would save about 5% per run. Not built.
- Why runs got slow: 955-2045 calls per 3-day run in week 5, against about 404 when #20 was filed.
  Nearly every event is talk. Recorded as a finding, not patched.
- Built instead:
  1. Thoughts in parallel. All villagers think at the same minute, and one villager's thought never
     changes another's prompt, so the calls go out together and are applied in sorted id order.
     Same prompts, same records, same order as the serial loop.
  2. Several runs at once: `OLLAMA_NUM_PARALLEL=4` on the PC and 3-4 runs side by side.
     Each run is as slow as before, but the 21 runs take about a third of the time. No engine change.
- Check: same belief log, memories and event log as the serial loop with a fake model (tests),
  then the minutes per run and per batch of runs on the PC.

## 2. Villager memory, ideas taken from Hermes Agent (not the tool itself)
- **Recall:** a private choice, `recall <words>`. The villager searches its own memories (full-text)
  and sees the best matches before it acts or thinks. It decides when and what to search. Nothing is recalled for it.
- **Notebook:** a short private notebook per villager: one part about itself, one line per person it knows.
  Only the villager writes it, in its own words, when it thinks ("keep / rewrite this line").
  The code only stores it, limits its length, and shows it back to that villager. No code summaries.
- Logged for analysis, like beliefs. Never a world event, never in the state hash.
- Out of scope: Hermes-style skills and sub-agents.
- Two small fixes from week 5, both plain facts, no hints:
  - Clearer look memories (#49): "People here: Bob (npc_bob). The body of Mayor Aldric (npc_mayor) lies here."
  - Arrest takes an optional reason in Hal's own words, logged with the event and never checked (#50).

## 3. A judge for evaluation: Kev (local, Apache-2.0)
- Kev-4B on the PC answers yes/no, choice and score questions with probabilities. Run only AFTER the
  village runs (one GPU), never inside a run, so runs stay deterministic.
- Questions per run: does the talk really accuse or defend the tagged person (vs the name check, #35/#47)?
  Do the cited memories support the suspicion (score)? Does a thought misread a memory (e.g. "Bob is dead")?
- Check first that Kev-4B runs on the 5090 next to Ollama. If not, use qwen as the judge with the same questions.
- Spot-check the judge by hand on 30 items before trusting it.

## 4. Runs
- **Main grid (with memory):** 5 seeds x 3 scripts (none, blame_hal, accuse_victor) = 15 runs.
- **Baseline (week 5 code, no memory):** 3 seeds x none = 3 runs. Same seeds, so the memory effect is visible.
- **Model check:** 1 seed x 3 scripts with a Hermes model in Ollama instead of qwen = 3 runs.
  Tells us if outcomes like "Hal arrests Bob" come from the setup or from one model.
- 21 runs, about 22 hours of model time, about 7-8 hours with 3-4 runs at once. Overnight batches.

## 5. Measures (`whisperwick eval`)
- Outcome per run (world facts only): who is held at the end, right / wrong / nobody.
- Divergence: on the same seed, do different player scripts end differently?
- Valid sources: % of beliefs whose cited memories exist (code) and support them (judge).
- Memory slips: thoughts that misread a memory (judge), with vs without memory.
- Coherence: a judge score per day of story, plus my own ranking of 5 stories.
- Autonomy: aims formed, done and dropped; arrests and releases; stalls.

## 6. Demo and write-up
- `whisperwick play` as a short playable demo (1 day, you are Wren), with `outcome` at the end.
- A write-up on the wiki: what worked, what didn't, the numbers, the Gate 2 decision.
- A visual replay preview: one self-contained HTML page per run that replays the event log
  (who is where, who says what, arrests), to see what a front-end could show. Read-only, world facts only.

Gate 2 is Donovan's call after playing the demo. The numbers and thresholds below are inputs to it.

## Gate 2 (proposed thresholds, yours to change)
- **GO** (start a front-end): outcomes differ by player script on most seeds, valid sources >= 95%,
  and stories read as coherent.
- **PIVOT:** outcomes rarely depend on the player, or memory slips stay common even with memory.
- **STOP:** stories are incoherent or untraceable.

## Tasks and order
1. Parallel thoughts + several runs at once (#20). 2. Recall + notebook. 3. eval command + Kev judge. 4. Runs. 5. Demo + write-up + Gate 2.
Sonnet subagents implement and write tests; I review every diff and run verify-world-engine after 1.

## Out of scope
More villagers, escape, daily routines, economy, 3D, the 8B model tier.

## Risks
- Parallel thoughts could change the order of records: the determinism checks must stay green.
- Recall and notebook make prompts longer: watch speed and context size.
- The judge can be wrong: hand spot-checks, and the judge never feeds back into a run.
- 21 runs is a lot of PC time: if it slips, cut the model check first.
