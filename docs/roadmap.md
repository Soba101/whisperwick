# Roadmap: the player changes the story

Long-term goal: a Skyrim-like world where agents keep a story moving,
and the player's actions change where it goes.
This 6-week prototype proves the "brain" in text. Graphics come later (v0.2+).

## The question (updated after week 2)

Can a player's actions change an emergent story,
while the story stays coherent and every belief stays traceable to its source?

- **Changes:** the same seed ends differently depending on what the player does.
- **Coherent:** a reader can follow it (human rank + judge).
- **Traceable:** every belief an NPC holds points back to an event in the engine log.

## Weeks

| Week | Focus | Exit check |
|---|---|---|
| 1 | Engine skeleton | Done: a seeded run replays identically |
| 2 | Vertical slice (local model) | **Gate 1:** a readable murder story from 5 NPCs |
| 3 | Player + real objects | Same seed, 3 player scripts, 3 different outcomes |
| 4 | Beliefs and rumours | A player's lie can be traced: who believes it, and via whom |
| 5 | Consequences + endings | Story ends in an engine-decided outcome (arrest, escape, wrong arrest) |
| 6 | Evaluate + playable demo | **Gate 2:** GO (front-end) / PIVOT / STOP |

### Week 3: player + real objects
- The player is an actor like any NPC. Their intents come from the terminal
  (`whisperwick play`) or from a script file (repeatable runs).
- Real objects in the engine: the knife, Victor's muddy boots. Verbs: `take`, `give`, `show`.
  Evidence that exists in code is evidence NPCs can find, hide or show. (Also helps #11.)
- Three player scripts on one seed: do nothing / tell Bob "Hal did it" / hide the knife.

### Week 4: beliefs and rumours
- Each NPC holds beliefs ("Victor is the killer") with a source: saw it, was told by X, reasoned.
- Rumours spread through talk, and trust in the source matters (including trust in the player).
- Fixes #11 (no invented facts: a claim needs a source) and #12 (talk loops).

### Week 5: consequences and endings
- An `accuse` action. The guard arrests when enough villagers believe the same thing.
- Outcomes are engine facts: the right person arrested, the wrong person, or the killer escapes.
- A light "director" nudges pacing if nothing happens for too long.

### Week 6: evaluate and demo
- 5 seeds x 3 player scripts. Measure: outcome divergence, coherence, % of beliefs with a valid source.
- Compare with beliefs switched off (the Generative Agents style baseline).
- A playable terminal demo and a short write-up.

## Deferred to v0.2
- 20+ NPCs and a cheap 8B model tier.
- A 3D front-end (Unity or Godot) that sends intents to this engine.
