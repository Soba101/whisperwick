# Week 7 plan: make the villagers work

Goal: make the NPC layer work before anything else (Donovan, 2026-10-12). Find out why villagers loop,
arrest on weak evidence, stall and leak secrets, using measures first. Gate 2 waits; no front-end.
Donovan after playing the demo (2026-10-14): "still 50/50 on the game itself", so keep building first.
If the NPC layer cannot be made to work, Donovan may repurpose the engine (the scheduler, memory, cited
beliefs and eval tools are generic; only the scenario, arrest actions and outcome reader are murder-specific).

"Working" means five checks, each measured, not felt:
- Coherent: no loops or self-contradiction; a reader can follow what happened.
- Grounded: nearly every belief cites a real memory; few hunches.
- Not a pushover: villagers do not simply believe whatever the player says.
- Decisive: Hal acts on his doubt (moves, asks, looks) instead of standing still for days.
  Not arresting is his right; the check is that he does something to find out, not that he arrests.
- Different story, same seed: what the player does changes what happens.
Donovan's own read after week 6: "not that interesting" - Victor ends up held whatever the player does.

What week 6 showed (issues #53-#60):
- After an arrest the village loops for about 3 days: 604 more talk events, Hal repeating one line
  about 40 times (#60). The Stalls measure says 0 because villagers still produce events.
- Memory off: Hal arrested Sarah twice on weak evidence (#57, #60). Memory on: Victor held in 13/15 (#54).
- Hal stalls (checked 2026-10-14): no arrest in s2-none-off, s4-blame_hal, s5-blame_hal. He holds the
  Town Hall for about 2 days: "wait for seal identification", "I do not guess", "wait for warrant".
  In s2 and s4 he never leaves the Town Hall; in s5 he moves twice. He never goes to ask whose seal it is.
- Victor says his private evidence memory out loud in 6/15 runs (#56).
- The player changed the ending on 2/5 seeds (#55). Not in scope this week.
- Model errors: s3-none-off had 2 (both in the last hour, likely the interview); the wiki says 0.
  No "HTTP 400" text is in its log. The other 18 week 6 logs show 0. Correct the wiki.
- Since the week 6 runs, the scheduler has conversational turn-taking. Week 6 numbers are not directly
  comparable with new runs.

Rules carry over: world is physics only; villagers decide what they believe, want and do;
no director, no formulas deciding opinions, no hints in prompts. Stalls and odd outcomes are findings.

## 1. A loop measure (read-only, no engine change)
- Why: the loop is invisible today. Stalls counts hours with no event, not hours with nothing new.
- A near-copy measure does NOT work, so it is dropped: Hal rewords and counts ("Forty-nine times. ...").
  Word-overlap repeat share is LOWER in the loop run than in healthy runs (0.21 vs 0.36-0.51).
- Lead measure, `after_arrest`: villager events after the last arrest that are not talk. Week 6 data:
  | run | events after arrest | not talk |
  |---|---|---|
  | w6-s42-none-off (loop) | 610 | 6 |
  | w6-s5-none | 842 | 27 |
  | w6-s3-none-off | 1098 | 31 |
  | w6-s1-none | 810 | 92 |
  | w6-s2-none | 1040 | 91 |
  | w6-s1-accuse_victor | 1298 | 131 |
- It is weak on its own (s5-none and s3-none-off are low too). Add a second signal: new claim subjects,
  items or places mentioned per hour after the arrest. Keep whichever separates the loop run.
- Also a stall measure for "Decisive": hours Hal spends in one place with no move/take/show/look.
- Add to `eval_measures.py` (new small file if it grows past ~200 lines); show in `eval` and `compare`.
- Check: unit tests with a fake event list; then the table above reproduced by the code.

## 2. Call logging (small, before any runs)
- Per run: request count, prompt and output tokens, latency (mean and p90), errors with their HTTP code.
  llama-server already returns token counts and timings in each reply; read them, add no new calls.
- Written to the sidecar JSON and shown in `eval`. Needed before any speed claim.
- Also print each model error's reason in the run log, so the next s3-none-off is easy to explain.
- Check: unit test with a fake client reply; one short live run shows sane numbers.

## 3. Code walks the route the villager chose
- Why: today each step of a walk is one model call. Fewer calls, faster runs, and maybe fewer stalls
  (Hal could choose to go somewhere far in one decision).
- The villager still decides. Only the stepping moves to code:
  - `move` may name any known place, not just a linked one. The engine finds the shortest route
    (fixed order on ties, so the same seed gives the same events) and does one real `move` event
    per step, at normal walking speed. Every step is witnessed and remembered as today.
  - `find` a person: walk to where this villager last saw or heard of them, from its OWN memories.
    Never the person's true location. If it has no memory of where they are, the intent is rejected.
  - The walk stops when the villager arrives, or when something it would wake for happens (spoken to,
    sees someone arrive). Then it is asked as usual. Held villagers cannot walk (custody rules stay).
- Prompts change only to say the target can be any place or person. No hint about where to go.
- Check: unit tests (route, tie order, interrupted walk, unknown person rejected, held villager);
  `verify-world-engine` skill (determinism, replay); one short live run reviewed by hand.

## 4. The two free llama-server speed tests (#59), before the runs
- `--spec-draft-n-max 2`, then context checkpoints with a small min step and one slot per villager.
- Measure with the new call logging on the same short run. Keep the faster setting for all runs below.
- No code change. Needs the PC with nobody playing; the PC session may restart llama-server.

## 5. Control runs, to learn if recall and the notebook cause the better behaviour (#54)
- After 1-4 are merged. Memory on AND off, `none` script, seeds 1-5 and 42: 12 fresh runs.
  The old seed-42 off run (#60) used older code, so it no longer counts.
- Report held person, the loop and stall measures, arrest reasons, calls and tokens per run.
- First fix the batch and judge scripts: they treat a stopped or half-failed run as finished (a sidecar
  exists). A run that stopped early must be rerun, not counted.
- Two at a time on the PC, overnight. No code change while runs go.

## 6. The killer leak (#56): look first, change later
- Trace which prompt part carries Victor's evidence line when he speaks (`whisperwick trace`).
- Count confessions to non-held people in the week 6 and week 7 runs.
- Only if the cause is a plain wording fact (e.g. a secret shown in the same block as things to say),
  propose a neutral rewording. No "do not confess" instruction. Donovan decides before any change.

## Out of scope
- Player influence (#55), speed code changes beyond the free tests (#53, #59), Kev judge accuracy (#58),
  claim tags (#51), aims as statuses (#52), the NVFP4 or MoE model, 3D, front-end.

## Exit check
- A table over the 12 runs scoring the five "working" checks (loop and stall measures, held person,
  calls and tokens).
- A written finding on whether memory changes Hal's arrest choice, and whether code walking changes
  calls per run and Hal's stalls.
- Each finding gets a GitHub issue (label `finding`); wiki Findings and Run Results updated
  (including the s3-none-off error fix).
