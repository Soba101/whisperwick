# Week 4 plan: beliefs, rumours and trust (revised)

Goal: every villager is a separate person who works out for themselves what happened.
They have their own personality, memories and convictions. They decide who to suspect
and who to trust. The code only keeps track of where each belief came from.
Exit check: **a player's lie can be traced: who believes it, and via whom.**
Fixes #11 (invented facts) and #12 (talk and show loops). Covers #23 (killer gives away evidence).

## Why this was revised

The first version did the thinking in code: starting suspicion as numbers, "the knife points to Victor",
and a formula that moved beliefs when someone heard a claim. The prompt then told each NPC
"Victor did it: 65%". The agents acted out conclusions the code had reached.
That version stays in the repo as a baseline (runs `w4-none`, `w4-blame_hal`, `w4-hide_knife`).

## The split

- **World: physics, not a storyteller.** It never chooses what anyone does, says or believes,
  and never pushes the plot. It only does what reality does: you cannot take a knife that is
  in another room, people in the room hear what you say, a given item changes hands.
  This keeps lies as lies: saying something does not make it true. Unchanged.
- **Code: where things came from.** Every memory keeps the id of the event behind it.
  Every belief an NPC states must cite memories it really has. The code checks the citations.
  It never decides what anyone believes.
- **Agents: everything else.** Each villager acts like a real person: it decides what to do and say,
  whether to lie, who it suspects, how sure it is and who it trusts, in its own words,
  from its own memories and personality.

## Design

- **Personality** (scenario, per NPC): 2-3 sentences of temperament and convictions,
  e.g. how they treat strangers, gossip and proof. Character, not plot.
  Bob is blunt and trusts his own eyes; Alice is warm and loves news; Sarah wants proof;
  Hal is dutiful and wary of newcomers; Victor is charming and calculating.
  Victor's motive (not being found out) is his conviction, in his own memory.
  The one-sentence goals from the first version are removed: they were written for the villagers, not by them.
- **Memories cite events.** `Memory` gets `event_id`. Starting evidence gets ids like `start:npc_bob:0`.
- **Thinking.** Every 4 game hours, and at bedtime, each NPC reflects (replaces the nightly-only reflection).
  It returns JSON: `thoughts`, `suspect` (a person id or null), `sureness` (low / medium / high),
  `because` (ids of memories it relies on), and `trust` (for people it has met: low / medium / high + why).
- **Checking.** Cited ids that the NPC does not actually have are dropped and counted.
  A suspect with no valid citation is kept, but marked as a hunch. That is the #11 measure.
- **Prompt.** The NPC sees its personality, and its latest belief and trust in its own words
  ("You suspect Victor, quite sure: ..."). No numbers from code, no "this points to you" marks.
- **Claims stay.** A talk may carry `claim: {kind, subject}`. This is the NPC choosing to accuse
  or defend someone out loud. It makes speech traceable; it does not change anyone's mind by formula.
- **Belief log.** Each belief is saved with its time and citations in a JSONL file next to the run
  (beliefs are model output, so they are not world events).

## Trace

`whisperwick trace X.db npc_hal`: everyone who suspected Hal, and the chain behind each belief.
For a cited "Bob told me Hal did it" (event 88): look at what Bob believed or had heard about Hal
before event 88, and keep going. It ends at something seen first-hand, at someone talking about
themselves, or at "no source: made up" (the player's lie).

## Tasks

1. **Undo the formulas.** Remove numeric beliefs, clue mapping, trust math, the belief % in the prompt,
   the "points to you" marks and the goals. Keep claims, the repeat guard (#12) and the trace command shell.
2. **Personalities + memories with event ids.** Scenario `personality`; `Memory.event_id`; prompt shows personality.
3. **Thinking and the belief log.** Structured reflection every 4 hours and at bedtime, citation checks,
   JSONL belief log, latest belief and trust shown in the prompt.
4. **Trace and report.** Rebuild `trace` on the belief log; interview and `compare` read the last belief;
   claim and hunch counts in the report.
5. **Runs.** Smoke run, then none / blame_hal / hide_knife. Compare with the formula baseline.

## Who does what
- Sonnet subagents implement and write tests. I review every diff, run tests + ruff, and
  verify-world-engine if the engine is touched. Commits on the Mac.

## Week 5 changes because of this
- No engine rule that arrests someone "when enough villagers agree". Hal, the guard, decides
  whether and whom to arrest, like a real guard. The world only carries it out (the person is held).
- No "director" that nudges pacing. If the story stalls, that is a finding.

## Risks
- **More model calls.** Thinking every 4 hours adds about 20 calls a game day (~15%).
- **The model cites badly.** It may cite memory ids that do not fit. Checking catches fake ids, not weak reasoning.
- **Slower convergence.** Real people may never agree. That is fine; week 5 decides what happens then.
