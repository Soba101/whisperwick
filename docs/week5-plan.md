# Week 5 plan: consequences and endings

Goal: what villagers do has lasting consequences in the world, and the story can end in an outcome
the world records (the right person held, the wrong person held, or the killer still free),
without a director and without the code deciding what anyone believes or wants.

Exit check: **each villager chooses its own actions and can form and revise its own short-term aims.
Valid actions have lasting consequences. Every arrest and release can be traced from the villager's
own thinking to the world event. No-player runs show what the village does on its own, stalls included.
Different player actions can lead to different outcomes.**

Fixes #35, #36, #24. Builds on the week 4 design: villagers think for themselves; the world is physics only.

## 1. Belief, intention and speech are three separate things (#35, #36)

- **Private belief:** who I really think did it. This is the existing `suspect`, now described plainly as
  "who you truly believe did it". Victor can answer "me".
- **Intended accusation (new):** who I mean to blame out loud, if anyone (`will_accuse`).
  It may differ from my belief. That is how lying is recorded honestly.
- **Public statement:** what was actually said. The claim tag becomes two clearer fields,
  `accuses` and `defends` (a person id or nothing), replacing `claim_kind` + `claim_subject`.
- **Mismatch check:** if a tag names someone the message never mentions, the claim is kept in the log
  but marked `unverified`. It is not shown to listeners as a tag, so a bad tag cannot mislead anyone.
  The code never forces anyone to tell the truth.

Test: Victor privately believes "me", intends to accuse Hal, says so, and all three records are separate and traceable.

## 2. Arrests are world facts (#24)

- A new action, `arrest <person>`. Only someone with authority can arrest: scenario `authority: [npc_hal]`,
  a fact about the world, like who holds which item. Hal decides by himself whether and whom to arrest.
- The world checks the physical rules: the arrester has authority, is in the same place as the target,
  and the target is alive and not already held. Otherwise the action is rejected with a reason and nothing changes.
- **Custody** is a world state: a held person cannot move, take, drop or give. They can still talk and look.
  Everyone present witnesses the arrest, and the news spreads only by talk.
- `release <person>`: the arrester can let them go.
- Escape is **not** in this week. It needs a fair physical rule, and the outcomes below work without it. It is noted for later.
- Saying "you're under arrest" does nothing by itself. The prompt says arrests only happen through the action.
- No rule ever arrests someone because villagers agree.

## 3. Short-term aims, chosen by the villagers (agent-authored goals)

- When it thinks, each villager may also state a short aim in its own words ("find out where Victor was last night"),
  and say whether it is new, continuing, done or dropped.
- The aim is private, shown only in that villager's own prompt, and logged for analysis. It is not a world event.
- No code ever assigns an aim. The thinking prompt asks "Is there anything you want to do?"
  and "nothing in particular" is a fine answer.

## 4. Tracing consequences

- `whisperwick trace DB --event N` explains any action, for example an arrest:
  who did it, what they believed and intended at the time (their latest thinking before the event),
  the memories they cited (or "acted on a hunch"), and whether the world accepted or rejected it.
- `whisperwick outcome DB` reads **only world facts**: who is held at the end, and when each arrest or release happened.
  It never reads dialogue. The run does not stop at an arrest: the village keeps living, and objections and releases can happen.

## Tasks

1. **Belief / intention / speech** (#35, #36): thinking schema (`will_accuse`), talk fields `accuses` / `defends`,
   the mismatch flag, memory text, and trace updates.
2. **Arrest, release and custody** (#24, engine): the actions, authority, custody rules, save/load, the state hash and invariants.
   The golden snapshot will change on purpose. Run verify-world-engine.
3. **Aims:** thinking schema + prompt + log.
4. **Trace + outcome:** `trace --event`, `outcome`, and compare columns for the outcome and aims.
5. **Runs:** a 1-day smoke run, then none, blame_hal and hide_knife for 3 days each. Plus an `accuse_victor` script, where the player
   tells Hal "Victor did it" with nothing to show for it. The no-player run is the autonomy check: record actions,
   aims formed, changed or dropped, disagreements, arrests, and stalls (stalls are findings, not something to patch).

## Who does what
Sonnet subagents implement and write the tests. I review every diff, run the tests and ruff, and run verify-world-engine after task 2.
Commits are made on the Mac. Order: 1 → 2 → 3 and 4 in parallel → 5.

## Out of scope
Escape, a `leave the village` action, daily-life routines, economy, more villagers, parallel model calls (#20), 3D.

## Risks
- **Hal may never arrest anyone.** That is a real outcome ("the killer stays free"), not a bug. If it happens in every run, it is a finding for week 6.
- **Hal may arrest too fast,** for example the newcomer on a rumour. That is also a real outcome, and the trace will show why.
- **The mismatch check is crude:** it only checks for a name. It catches a tag that names the wrong person,
  but not "accuses" vs "defends" mixed up for the same person. Measure how often it fires.
- **The snapshot changes:** custody is new world state. The change will be reviewed before the snapshot is updated.
