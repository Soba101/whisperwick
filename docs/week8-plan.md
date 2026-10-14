# Week 8 plan (draft, for review)

Two tracks. Behaviour: fix causes week 7 found. Speed: make a game fast enough for real players,
with many villagers. Donovan (2026-10-15): one game takes far too long; a real game has many
villagers talking to each other and to players all the time.

Rules carry over: world is physics only; villagers decide what they believe, want and do;
no director, no formulas deciding opinions, no hints in prompts. A speed change may decide HOW OFTEN
a villager gets a turn, never WHAT it thinks. Every change is re-checked against the five week 7
checks (Coherent, Grounded, Not a pushover, Decisive, Different story) so speed does not buy worse villagers.

## Where week 7 left things
- Loops after the arrest (#61): with memory on, the claim-gap bar is met in 1 of 5 runs.
- Memory makes Hal more decisive (stall bar 5/6 vs 3/6) and a bit more often right (5/6 vs 4/6) (#62).
- Seed 3 holds Bob again, for obstruction (#48, #62). Hal ignored a confession he heard (#56).
- Starting evidence now sits under "What you knew before today:" (#56); not yet tested in a run.
- One call takes ~1.7 s alone; a 3-day village is ~1,000-3,400 calls, about 45 min or more of GPU.
  Two runs on one llama-server are slower than one at a time (#59).

## Speed track (measure first, keep only what helps)
Baseline: the same 3-game-hour run plus one 3-day run (seed 1, memory on), one at a time, with the
call logging (requests, tokens, latency). Each idea below is tested alone against that baseline.

1. Skip turns where nothing changed. A routine (hourly) turn for a villager that has seen or heard
   nothing new since its last turn is skipped. Only how often, not what. Watch the stall measure:
   Hal must still be free to act on his own.
2. Prompt diet. Prompts are ~1,800 tokens and reading them is ~half of each call. Remove repeated
   rule text and lines for features a villager cannot use right now (e.g. recall, used 4-42 times
   a run, is offered in every prompt). Same facts, fewer tokens.
3. Prompt reuse. llama-server already caches prompts: an exact repeat read in 95 ms vs 787 ms. Put
   the fixed text first and give each villager its own server slot (`id_slot`), so its next prompt
   reuses the start. Prompt order may change behaviour: check the five checks.
4. Level of detail. Villagers near a player act every minute; villagers elsewhere act less often.
   Biggest saving with many villagers; only scheduling, never content.
5. A faster model: one mixture-of-experts test (~3B active, maybe 3-5x per call). New behaviour
   baseline, so the five checks decide, not speed alone. Needs a download on the PC.
6. Feel (no speed change): stream replies word by word in the web demo.
7. Clean-up: a code audit for dead code (e.g. the `memory_lines` wrapper, the Ollama client if no
   run uses it), done by Codex; delete what is unused.

Not taking: Kev as a router for simple decisions (over 90% of calls are talk, which needs the main
model, and a router adds a call); an agent-to-agent chat framework (talk must go through the engine
so it has witnesses and a log; it would not cut calls). Group turns (one call writes a short
exchange, each line still a logged talk event) would cut talk calls but partly takes a villager's
own reply away: only with Donovan's OK.

## Behaviour track (Donovan picks which, before building)
- Loops after the arrest (#61): look at what villagers are shown after an arrest (e.g. their own
  last words) for a plain wording cause, as was done for #56. No "stop repeating" instruction.
- Hal ignoring a heard confession (#56): trace whether the confession reached his memories and
  prompt, or was crowded out (memory, not attention, may be the cause).
- Obstruction arrests (#48, seed 3): his personality line ("wary of anyone who tells him how to do
  his job") is the likely driver; it is character, not a bug. Record, do not patch, unless Donovan says.
- Test the evidence heading: the same 12-run grid would cost a night; a smaller check is seeds 1
  and 3, memory on, both layouts.

## Options for Donovan
- Kev judging: Kev's PyTorch on the PC is now CPU-only. Fix it (reinstall the CUDA build) or drop
  the Kev scores and rely on the code measures.
- Which speed items to run first (suggested order: 1, 2, 3, then 4; 5 only if they are not enough).
- Which behaviour items, if any, this week.

## Exit check
Per speed item: calls per run, seconds per call, total time, and the five checks vs baseline.
A written answer to: how long does one 3-day game take now, and what is the next biggest saving.
