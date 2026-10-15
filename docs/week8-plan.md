# Week 8 plan (approved 2026-10-15, done 2026-10-16)

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

Checked first (2026-10-15), before building:
- Item 1 is small and risky: a routine turn only fires after 60 quiet minutes, so "nothing changed" means
  dropping routine turns. At most 5 villagers x 16 waking hours x 3 days = 240 calls (<15% of a run), and
  routine turns are Hal's only unprompted chance to act (the Decisive check). Moved to last.
- Item 2 is small when safe: a rendered mid-run Hal prompt is ~985 tokens; cuts that keep every fact save
  ~100-150 (~10%, ~4-5% of a call). Bigger cuts (last-words list ~100, recall results that repeat memories
  ~200) change what the model sees. The reply schema is applied by the server, not read as prompt text.
- So the order is now 3 (prompt reuse), then 4 (level of detail), then 2 (safe cuts only, folded into 3's
  reorder), then 1. Measuring calls by reason (answer, overheard wake-up, routine) comes first: it says
  where the calls actually go.

Result of item 3 (2026-10-15): no gain on this model. qwen3.8 is a hybrid model; this llama-server build
reuses a prompt only when the exact same prompt repeats (95 ms vs 787 ms), not a shared start: a shared
1,700-token start reused 0 tokens, with or without a slot per villager and checkpoints. The reorder was
undone (behaviour stays comparable with week 7); the LLM_SLOTS option stays, off by default, for a
standard model or a newer server. Calls by reason are now logged (answer / woken / first / routine).

Where calls go (2026-10-15, 3-day run, seed 1, memory on, data/w8-base-s1): answer 1,043 turns (62%),
woken 516 (31%), routine 124 (7%), first 5; 1,884 requests, 2.34 s each, 73 min. So: conversations are
the cost. Rule-safe lever: wake bystanders less often (only when spoken to, named, or something other
than talk happens), up to ~30% of calls. Bigger lever, needs Donovan's OK: group turns for conversations.

Fewer bystander wake-ups (6a50ee5): talk wakes only the listener and named bystanders. Seed 1: requests
1,884 -> 601 (-68%), 73 -> 31 min, but Hal stalled 24 h and Bob was held (baseline: Victor, 2 h). One run
each, so a check on seeds 2-5 and 42, both versions, one at a time (data/w8-wake-*, w8-base-*), decides.
Result (seeds 1-5, memory on; seed 42 lost to a server outage): requests ~1,320 -> ~990 (-25%, not -68%),
right person 5/5 -> 2/5 (Bob 1, nobody 2), Decisive 4/5 -> 1/5 (stalls of 24-47 h). Fewer wake-ups means
fewer chances for Hal to act. Reverted. Side result: the code before it (with the evidence heading) held
Victor in 5/5 seeds, including seed 3 (week 7: Bob); one run per seed, so check before trusting it.

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
- Kev judging: fixed (CUDA PyTorch reinstalled, see the wiki Model Server page); week 7 runs being judged.
- Which speed items to run first (suggested order: 1, 2, 3, then 4; 5 only if they are not enough).
- Which behaviour items, if any, this week.
- Later, not this week: players bring their own model key (OpenAI-style endpoint) so games run in the
  cloud in parallel. Open questions on the wiki (Open Questions): cost per game, behaviour per model, key safety.

## Exit check
Per speed item: calls per run, seconds per call, total time, and the five checks vs baseline.
A written answer to: how long does one 3-day game take now, and what is the next biggest saving.

Evidence heading check (option 1, started 2026-10-15): seeds 6-10, memory on, one run at a time,
each seed with the heading (current code) and without it (week 7 code, 78daf17; the only prompt
difference). scripts/week8-heading-runs.sh, data/w8h-*. Seen so far, one run per seed: with the
heading Victor was held in 5/5 (seeds 1-5) and 4 of 5 arrests came on day 1 before noon; week 7
without it held Victor in 4/5 (seed 3: Bob), with later arrests.
Result (2026-10-16, #66): Victor alone held in 8/10 seeds (1-10) with the heading vs 4/10 without; better
on 4 seeds, worse on none. Bob held in 3/10 without it, 0/10 with. Decisive 7/10 vs 5/10; Coherent 2/8 vs
0/5; Grounded 95-100% both. Seeds 7 and 8 with the heading still stall (nobody held). A lead, not proof.
The heading stays (already in main).

## Next: a mixture-of-experts model test (approved 2026-10-15, after the heading check)
Why: one call takes ~1.5-2.3 s; a 3-day run is 50-75 min. A MoE model (e.g. Qwen3-30B-A3B, ~3B
active, ~18 GB at 4-bit) works through ~3B weights per token instead of 27B, so replies should be
written several times faster, and as a standard-attention model it should reuse prompt starts (#59),
which qwen3.8 cannot. Guess: ~0.4-0.7 s per call, ~15-25 min per run. Not measured.
1. Wait for the heading batch (data/w8h-*) to finish: it must stay on qwen3.8 to be comparable.
2. Download one MoE model on the PC (Donovan picks; needs his OK for the download).
3. A llama-server start script for it next to llama.cmd (Donovan creates or changes the task).
4. One timed 3-day run, seed 1, memory on (data/w8-moe-s1). Calls, s per call, total time.
5. Read it against the five checks (Coherent, Grounded, Not a pushover, Decisive, Different story).
   It is a new behaviour baseline: speed alone does not decide.
6. If ~3x faster and the checks hold: the seeds 1-5 grid on it, then try LLM_SLOTS prompt reuse.
Also check: does it fit on the GPU next to Kev (would end the server swap)?
Tracked in #63. After it: the same model on vLLM for several games at once (#64), one change at a time.

MoE result (2026-10-16, #63): Qwen3.6-35B-A3B Q4_K_M, seed 1, memory on (data/w8-moe-s1). Per request
1.03 s vs 2.34 s (prompt read 259 vs 745 ms), but 56% more requests (30% of actions rejected vs 6%),
so the run took 43 min vs 60 (1.4x). Hal held Bob ("sudden appearance at the scene"), arrested Victor
for obstruction and released him. Decisive and Coherent pass on this seed; right person fails. Below the
3x bar and fails a check, so no seed grid. Its draft model is downloaded but not tried.

## Exit answer (2026-10-16)
How long does one 3-day game take now? On qwen3.8 27B, one game at a time: ~1,100-2,100 model requests
at ~2.3 s each, so **about 45-75 minutes** (week 8 seeds 1-10: 1,107-2,099 requests). Unchanged from
week 7: every speed item tried this week was dropped or failed a check.

| item | calls | s per call | run time | five checks | kept? |
|---|---|---|---|---|---|
| skip routine turns | -7% at most | same | - | Decisive at risk | no (not built) |
| prompt diet | same | ~-5% | - | - | no (too small) |
| prompt reuse (#59) | same | same (0 tokens reused) | - | - | no; LLM_SLOTS kept, off |
| fewer bystander wake-ups | -25% | same | -25% | right person 2/5 vs 5/5, Decisive 1/5 vs 4/5 | no, reverted |
| Qwen3.6-35B-A3B (#63) | +56% | 1.03 vs 2.34 | 43 vs 60 min | right person fails (seed 1), 30% rejected | no |

Behaviour: the evidence heading holds the right person in 8/10 seeds vs 4/10 (#66). It stays.
Reliability: the heartbeat now restarts llama-server after 3 minutes down; batches wait for the server.

What is the next biggest saving?
1. Several games at once (#64, vLLM). It does not make one game faster, but it is what real players need:
   llama-server loses throughput with two games (4.2 vs 1.7 s per call), vLLM batches them.
2. Group turns for conversations (62% of calls are replies). The biggest cut per game, but it partly takes
   a villager's own reply away: only with Donovan's OK.
3. A model screen: replay a few hundred saved turns against a candidate model and count parse failures,
   engine rejections and time, in minutes instead of a 45-60 minute run per seed. It does not judge
   behaviour, but would have shown the MoE model's 30% rejections at once. New code: Donovan decides.
