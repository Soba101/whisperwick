# Week 9 plan (approved 2026-10-16)

The user's order: (1) a model screen, (2) group turns for conversations, (3) optional: vLLM (#64).
Week 8 is done (docs/week8-plan.md, exit answer): a 3-day game takes 45-75 min on qwen3.8 27B.

Rules carry over: world is physics only; villagers decide what they believe, want and do;
no director, no formulas deciding opinions, no hints in prompts. A speed change may decide HOW OFTEN
a villager gets a turn, never WHAT it thinks. Stalls and odd outcomes are findings, not patches.

## 1. Model screen

Why: the MoE test (#63) needed a 43-minute run to show that 30% of its actions were rejected.
A screen replays a few hundred saved turns to a candidate model in minutes. It only screens models
OUT. It never judges behaviour: a model that passes still needs full runs and the five checks.

### How it rebuilds a turn
Runs do not save prompts, but the engine is deterministic. So the screen re-plays a saved run
through the normal run loop (`run_llm`, unchanged) with a log-driven client instead of a model:
- an act call returns what the villager really did at that tick (its event in the event log;
  no event = the turn ended in a look),
- a thinking call returns the saved thought (beliefs.jsonl, turned back into reply fields:
  citations and notebook; none saved = the thought failed),
- a recall returns the saved search words (agent.jsonl, in order: one turn can recall twice,
  e.g. Sarah at tick 3593 in w8h-s6-head).
Thinking calls do not say which villager they are for. They run as a batch in sorted ids, with a
second round only for those who recalled. The client tells them apart by the villager id in the prompt.
The prompt each villager gets is then built by the same code as in the real run, from the same
memories, belief, notebook and repeat history. Engine actions use no random numbers today.

Self-check, before any model is asked: the re-played event log, belief log and final notebooks must
equal the saved ones. If they drift, the screen stops and says where. Codex tried this in its review
with a throwaway client: all 11 runs re-played exactly.
What it does not prove: rejected first tries and their retry prompts were never saved, so a picked
turn uses the turn's first prompt only, not the original retry. Runs do not save the code revision,
scenario contents or parallel/slot settings either; the drift check is the guard for those.

Source runs: only runs made with today's prompt code: data/w8-base-s1..5 and data/w8h-s6..10-head
(qwen3.8), and data/w8-moe-s1 (MoE). Not the `nohead` runs (older prompt).

### How it picks turns
- 300 act turns from w8-base-s1..5, picked with a fixed seed, in proportion to turn reasons
  (answer 62%, woken 31%, routine 7% in seed 1, plus every "first" turn). Saved as a turn list
  (run, tick, villager), so every model gets exactly the same turns.
- Plus 50 thinking calls from the same runs (they have their own reply format).
- A second list of 300 act turns from w8-moe-s1, as a cross-check (see bars).

### What happens at a picked turn
The candidate model gets the same messages and reply schema. Its reply goes through the same path
as a real turn: parse to an intent, repeat guard, `world.act`, and the one retry with the engine's
reason. All of it on throwaway copies: the world, the repeat history and the agent log (a successful
intent and a recall both write to those). The replay goes on with the saved action.

### What it counts (only things with a right answer in code)
- Replies that parse (act and thinking), and the error reasons.
- First try accepted / rejected by the engine / stopped by the repeat guard; accepted after the retry;
  fell back to a look. Rejection share = rejected / calls, the same as a run's `stats` (rejected includes
  repeat-guard hits). The engine's reason for each rejection is saved too (runs never saved it: of
  MoE's 836 rejections, 217 were repeats and the rest have no reason on file).
- Requests per turn (the MoE run needed 56% more), recalls asked for.
- Seconds per call (mean, p90), prompt and output tokens (from the existing call logging).
- Thinking: share of beliefs whose citations name a memory id that exists. A code fact, not a judgement.

### Bars, set before any run
Known numbers from the runs' own stats: qwen3.8 rejects 2.5-5.8% (10 runs), MoE 30.4% (one run).
- Replay check: 11 of 11 source runs re-play exactly (events, beliefs, notebooks).
- qwen3.8 on the qwen turn list: rejection share within 3 points of its runs (so 1-9%).
- MoE on the qwen turn list: at least 15% and at least 2x qwen's screen share. This is a guess to test,
  not a known fact: on qwen's turns MoE may never reach the loops where it failed. If it misses, that
  is a finding, and the MoE turn list says whether MoE only fails in its own context.
- Time: one model, 350 picked turns and thoughts (plus their retries and recalls), under 15 minutes.
- Rule for later models: screen share over 2x qwen's, or under 98% replies that parse = no full run.

### Code (Codex builds, small files, lots of comments)
- `screen_turns.py` (pick and save the turn list), `screen_replay.py` (log-driven client, drift
  check), `screen_score.py` (counts), a `whisperwick screen` command, results as JSON plus a table.
- Tests: a short stub run re-played gives an identical event log; a fake candidate that always
  rejects or never parses gives the expected counts; a candidate's accepted action leaves the replay's
  world, history and agent log unchanged.
- Running it on MoE needs llama-moe.cmd on port 8080 on the PC: `touch data/server-watch.pause` first,
  remove it after, then llama-server back.

## 2. Group turns for conversations

Why: 62% of turns are replies (data/w8-base-s1). Talk comes in long runs at one place: in seed 1,
1,416 talk events in 117 runs (lines at one place, at most 5 minutes apart), 13 of them 12+ lines long;
49 runs have two speakers, 13 have three or four. One call writing a few lines instead of one call per
line is the biggest saving per game. A long talk then costs 3 calls per 5 lines (own reply, exchange,
own turn) instead of 5, so answer calls fall ~40%. Guess, not measured: 20-25% fewer requests per game.
Longer exchanges save more but write more of a villager's words; 3 lines is the starting point.

### Design
- A talk from A to B gives B an answer turn, as now: B's own call, full private prompt. B's reply is
  B's own choice (agree, deny, ask, say something private, or walk off).
- Only after that may an exchange call write the next lines: up to 3, A then B then A, two speakers
  only. Then B gets a normal own turn again. So both ends of every exchange are own turns.
- Each line is logged as its own talk event with the witnesses there, so memories, witnesses and the
  replay work as now. Each line passes the normal talk checks; a line that fails ends the exchange.
- Scheduler rules (to fix before building, they are the hard part):
  - Queued lines come first at their minute; while a line is queued, the speakers' ordinary answer
    turns for that exchange are not scheduled (that is the saving).
  - The queue is dropped, and the speakers get ordinary turns, if either leaves, dies, falls asleep,
    is held, or a third villager talks to either of them.
  - Bystanders are woken after each logged line, as now, so they can cut in (week 8: waking bystanders
    less made Hal far less decisive).
  - The own turn after the exchange is always scheduled, at the minute after the last line.
- What the exchange call sees, defined by events, not text: events both speakers witnessed (by event
  id), written by the engine's neutral describe, never from either one's memory text; world facts both
  can see now (where they are, who is there); each one's personality; and talk both heard, as "X said
  ..." (that it was said, not that anyone believes it). It does NOT see looks, starting evidence,
  private memories, beliefs, aims or notebooks. So it cannot put one villager's knowledge in the other's
  mouth, and it cannot use Victor's guilt for him.
- Lines from an exchange carry no claim tag (accuses/defends). Claims only come from own turns.
- Off by default (setting), so the week 8 code stays the baseline.

### What stays each villager's own choice, and what does not
- Own: what it believes, suspects and wants (thinking is unchanged: one call per villager, its own prompt).
- Own: every action that is not talk (move, take, show, give, drop, look, arrest, release). Arrests stay
  Hal's own choice in his own turn.
- Own: starting a conversation, the first reply, the turn after every exchange, anything that uses
  private knowledge, every claim.
- Not own: the words of the up-to-3 exchange lines. The exchange writer knows neither speaker's beliefs
  or aims, so a line can agree, deny or disclose against what that villager wants, and the next own turn
  cannot unsay it. Those lines go into everyone's memories and thinking like any talk.
This is the part the user must OK under "villagers decide what they believe, want and do". If the
answer is no, group turns are dropped; there is no version that writes a villager's words for it and
keeps them fully its own.
Known risk: Hal questioning Victor in an exchange cannot use his own evidence, so the questions get
weaker until his next own turn. That may cost Decisive or the right person; the bars below will show it.

### Five checks test (bars set before the runs)
Same as the baselines: 3 days, memory on, `none` script, one run at a time, seeds 1-10.
Baseline: data/w8-base-s1..5 and data/w8h-s6..10-head (#66), numbers from `whisperwick eval`.
| check | baseline (with heading) | bar with group turns |
|---|---|---|
| Right person held (Victor alone) | 8/10 | at least 7/10 |
| Wrong person held at the end | 0/10 | 0/10 |
| Decisive (GuardStall < 6 h) | 7/10 | at least 6/10 |
| Coherent (ClaimGap < 16 h, runs with an arrest) | 3/8 (s2 13 h, s3 15.9 h, s10 15 h) | at least 3 of its runs with an arrest |
| Grounded (suspect thoughts with at least one valid citation) | 98-100% | at least 95% |
| Model requests per game (`usage.requests`) | 764-1,884 | at least 20% fewer than the same seed |
| Different story | not measured | accuse_victor and blame_hal, seed 1, with and without group turns: same held person and arrest day within 1 day |
| Not a pushover | not measured | in those runs, nobody arrested because of the player's claim alone (read by hand, against the run without group turns) |
ClaimGap only counts tagged claims, so with group turns it measures own-turn claims only; untagged
accusations in exchanges still reach memories. Read it with that in mind.
Seeds 1-5 first. If right person is under 4/5 or Decisive under 3/5 there, stop: a finding, no seeds 6-10.
Also read the exchanges by hand on one run: do lines follow on, does anyone say what they could not know?

## 3. Optional: vLLM for several games at once (#64)
Only after 1 and 2. Uses the screen first to pick a model that vLLM can serve. Steps as in #64.

## Order of work
1. Screen: Codex builds, I review every diff, pytest + ruff, commit. Replay check on the 11 runs.
2. Screen qwen3.8 (llama-server as is), then MoE (swap on the PC, pause file). Finding issue, wiki, note.
3. Group turns: build only after the user OKs section 2. Then seeds 1-5, read, then 6-10.
4. Optional: vLLM (#64).

## Needs the user's OK
- This plan (rule 7).
- Group turns under the rules: up to 3 lines written from shared events only, between two own turns,
  no claims in exchange lines. Or say what must change, or drop it.
- Swapping llama-server for llama-moe on the PC for the MoE screen (about 15 min).
- Any download of a new model to screen.

## Exit check
Screen: the bars above, met or not, with the table for both models. Group turns: the five checks table,
requests and minutes per game vs baseline, and a plain answer: does it fit the rules, and is it kept?

## Result of item 1 (2026-10-16, #67)
Model screen built (`whisperwick screen check|pick|run|table`, ed5bee6). Every bar met. Replay rebuilds 11 of 11
runs exactly. qwen3.8 rejects 5.1% on qwen's turns, MoE 17.0-18.1% (3.3-3.5x), each screen 10-14 minutes.
On its own run's turns MoE rejects 32.7%, close to the run's 30.4%: about half of that is its own loop
(re-arresting Bob), half are malformed actions it makes anywhere. Use 127.0.0.1, not localhost, on the PC.

## Result of item 2 (2026-10-16, #68)
Group turns built (b11b578; each line names its speaker since 3b5e6d1, after a smoke run showed lines in the
wrong voice), off by default. Seeds 1-5 (data/w9g-s*-none-on): Victor held 2/5 (baseline 5/5), Bob 2/5,
nobody 1/5; Decisive 1/5 (baseline 4/5). Stop rule met, so no seeds 6-10 and no player-script runs.
Requests: -17% to -61% on seeds 1-3, +73% and +125% on seeds 4-5 (written lines wake bystanders and keep talks
going); the batch took the same total time. Seed 1 shows the cause: a shared line in Hal's name said Bob was
under arrest for obstruction, and two minutes later Hal arrested Bob for obstruction in his own turn.
Not kept. The code stays, off; keeping or deleting it is the user's call.

## Exit answer (2026-10-16)
- Model screen: done, every bar met (#67). A candidate model is screened in ~10-15 minutes (on the PC too).
  It caught the MoE model's malformed actions (17% vs 5% on the same turns). Use it before any full run.
- Group turns: fail the five checks and save no time over five seeds (#68). Words written for a villager
  become its commitments, and shared-only knowledge produces lines that ignore what a speaker knows.
  So conversation replies stay one villager, one call.
- One 3-day game still takes ~45-75 minutes on qwen3.8 27B. What is left for speed: several games at once
  (item 3, vLLM, #64), or a faster model that passes the screen and then the five checks.
- Item 3 (vLLM, #64): tested 2026-10-17, not adopted (thoughts time out; no total gain with 4 games).

## Result of item 3 (2026-10-17, #64)
vLLM v0.30.0 in Docker on the PC (WSL2 needed SVM on in the BIOS and the WSL 2.7.14 package), serving our own
qwen3.8 27B as 4-bit AWQ. Tested with the screen: 4 clients at once vs one. Under load vLLM answers act calls
~25% faster (3.3 vs 4.3 s), but 10-16% of its thoughts time out at 120 s, so 4 screens took 42 min vs 35 on
llama-server. Alone it is slower (2.49 vs 1.68 s). It is rejected less (2.0% vs 5.1%). Not adopted for now.
llama-server with 4 clients gives 1.6x the throughput of one game alone.
