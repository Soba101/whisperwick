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

## 1. Faster runs (#20)
- Villagers in different places think and act in parallel (Ollama serves a few calls at once).
  Same-place villagers stay in order, so whoever speaks first is still decided by the scheduler, not by timing.
- The event log stays deterministic in order (events are applied in a fixed order after the calls return).
- Target: a 3-day run in about 20-30 minutes instead of about 65.
- Model server, measured in this order (stop at the first that hits the target):
  1. Ollama with `OLLAMA_NUM_PARALLEL=4` on the PC. One setting, no new server.
  2. llama.cpp's own `llama-server` on Windows: parallel slots, prompt-prefix reuse, JSON grammars.
  3. vLLM or SGLang: the fastest at batching, but Linux only (WSL2 on the PC). Only if we ever accept that.
- Measure each the same way: minutes per 3-day run, errors, rejection rate, same seed.
  Speed alone barely helps (one call at a time): the gain comes from sending calls in parallel.

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
- 21 runs, about 11 hours with parallel calls. Overnight batches.

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

## Gate 2 (proposed thresholds, yours to change)
- **GO** (start a front-end): outcomes differ by player script on most seeds, valid sources >= 95%,
  and stories read as coherent.
- **PIVOT:** outcomes rarely depend on the player, or memory slips stay common even with memory.
- **STOP:** stories are incoherent or untraceable.

## Tasks and order
1. Parallel calls (#20). 2. Recall + notebook. 3. eval command + Kev judge. 4. Runs. 5. Demo + write-up + Gate 2.
Sonnet subagents implement and write tests; I review every diff and run verify-world-engine after 1.

## Out of scope
More villagers, escape, daily routines, economy, 3D, the 8B model tier.

## Risks
- Parallel calls could change event order: the determinism checks must stay green.
- Recall and notebook make prompts longer: watch speed and context size.
- The judge can be wrong: hand spot-checks, and the judge never feeds back into a run.
- 21 runs is a lot of PC time: if it slips, cut the model check first.
