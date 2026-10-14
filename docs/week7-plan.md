# Week 7 plan: make the villagers work (draft, for review)

Goal: make the NPC layer work before anything else (Donovan, 2026-10-12). Find out why villagers loop,
arrest on weak evidence and leak secrets, using measures first. Gate 2 waits; no front-end.
If the NPC layer cannot be made to work, Donovan may repurpose the engine (the scheduler, memory, cited
beliefs and eval tools are generic; only the scenario, arrest actions and outcome reader are murder-specific).

"Working" means five checks, each measured, not felt:
- Coherent: no loops or self-contradiction; a reader can follow what happened.
- Grounded: nearly every belief cites a real memory; few hunches.
- Not a pushover: villagers do not simply believe whatever the player says.
- Decisive: Hal reaches his own decision (arrest or not) instead of stalling ("cannot tell whose seal",
  "waiting for a magistrate", seen in s2-none-off, s4-blame_hal, s5-blame_hal).
- Different story, same seed: what the player does changes what happens.
Donovan's own read after week 6: "not that interesting" - Victor ends up held whatever the player does.

What week 6 showed (issues #53-#60):
- After an arrest the village loops for about 3 days: 604 more talk events, Hal repeating one line
  about 40 times (#60). The Stalls measure says 0 because villagers still produce events.
- Memory off: Hal arrested Sarah twice on weak evidence (#57, #60). Memory on: Victor held in 13/15 (#54).
  One control run cannot separate the causes.
- Victor says his private evidence memory out loud in 6/15 runs (#56).
- The player changed the ending on 2/5 seeds (#55). Not in scope this week.
- Since the week 6 runs, the scheduler has conversational turn-taking (someone spoken to answers the
  next minute; a speaker waits up to 5 min). Conversations, and maybe loops, now behave differently, so
  week 6 numbers (Victor held 13/15) are not directly comparable with new runs.

Rules carry over: world is physics only; villagers decide what they believe, want and do;
no director, no formulas deciding opinions, no hints in prompts. Stalls and odd outcomes are findings.

## 1. A loop measure (read-only, no engine change)
- Why: the loop is invisible today. Stalls counts hours with no event, not hours with nothing new.
- A near-copy measure does NOT work, so it is dropped. Hal never repeats a line exactly: he rewords and
  counts ("Forty-nine times. ..."). Word-overlap repeat share is LOWER in the loop run than in healthy runs
  (0.21 vs 0.36-0.51 at overlap 0.4).
- Lead measure, `after_arrest`: villager events after the last arrest that are not talk (move, take, show,
  give, release, arrest). Checked on week 6 data (2026-10-14):
  | run | events after arrest | not talk |
  |---|---|---|
  | w6-s42-none-off (loop) | 610 | 6 |
  | w6-s5-none | 842 | 27 |
  | w6-s3-none-off | 1098 | 31 |
  | w6-s1-none | 810 | 92 |
  | w6-s2-none | 1040 | 91 |
  | w6-s1-accuse_victor | 1298 | 131 |
- It is weak on its own: s5-none and s3-none-off are low too. Talkers per hour after the arrest does not
  separate them either (3.2 in the loop run, 2.5-4.1 elsewhere). Find a second signal before trusting it,
  e.g. new claim subjects, items or places mentioned per hour after the arrest.
- Add to `eval_measures.py` (new small file if it grows past ~200 lines); show in `eval` and `compare`.
- Check: unit tests with a fake event list; then the table above reproduced by the code.

## 2. Control runs, to learn if recall and the notebook cause the better behaviour (#54)
- Both memory on AND memory off, current code (with turn-taking), `none` script, seeds 1-5 and 42.
  Week 6 memory-on runs are not a fair baseline any more (see above), so each seed gets a fresh pair.
- The seed-42 memory-off run (#60) already ran on the current code (with turn-taking), so it counts as one of them.
- Report held person, the loop measure and arrest reasons per run. No code change while runs go.
- First fix the batch and judge scripts: they treat a stopped or half-failed run as finished (a sidecar
  exists). A run that stopped early must be rerun, not counted.
- Check the s3-none-off mismatch: its log shows HTTP 400 errors, but the wiki says 0 model errors.
  Count model errors per run from the logs, and correct the wiki if needed.
- About 11 runs, 2 at a time on the PC: about 8-10 hours, overnight.

## 3. The killer leak (#56): look first, change later
- Trace which prompt part carries Victor's evidence line when he speaks (`whisperwick trace`).
- Count confessions to non-held people in the 15 week 6 runs, with the repeat measure's text tools.
- Only if the cause is a plain wording fact (e.g. a secret shown in the same block as things to say),
  propose a neutral rewording. No "do not confess" instruction. Donovan decides before any change.

## Options for Donovan to decide (not built unless approved)
- Log real request counts, tokens and latency per run (cheap). Needed before any speed claim.
- Code carries out the aims villagers choose (walk the route, find the person) instead of one model call
  per step. The villager still decides the aim; code only does the steps. Fewer model calls, faster runs.
- Playtest notes from the web demo: add here once written down.
- The two free llama-server speed tests from #59 (fewer draft tokens, prompt checkpoints). No code change;
  needs the PC with nobody playing.

## Out of scope
- Player influence (#55), speed code changes (#53, #59), Kev judge accuracy (#58), claim tags (#51), aims (#52), 3D.

## Exit check
A table over 11+ runs with the loop measure, held person, and a written finding on whether
memory is what changes Hal's arrest choice. Each finding gets a GitHub issue (label `finding`) and a wiki update.
