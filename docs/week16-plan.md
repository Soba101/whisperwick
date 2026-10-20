# Week 16 plan (draft 2026-10-20): more things villagers can do

Rules carry over: the world is physics only; villagers decide what they believe, want and do;
no director, no formulas deciding opinions, no hints in prompts. Hal's arrests stay his own.
The model never changes the world: it proposes, the engine checks and records.

## Why this week
Donovan asked whether villagers can act more freely, and whether they can make up their own actions.
Today a villager picks from a fixed list (move, talk, take, give, show, use, look, wait; arrest and
release for Hal). An uncensored model would not change that: it only drops refusals, and the current
model refused nothing in the last 30 runs (week 13 and week 14 E1). The lever is the action list.

## What to build (Codex builds; I review and verify the engine)

### A. Gestures: free actions that change nothing
A villager may write a short action in its own words ("Alice paces by the window", "Bob wipes his hands").
- The engine logs it as a `gesture` event seen by people in the same place, like talk. No state changes.
- Refused when it claims a physical result the engine did not record (taking, opening, hitting, hiding,
  moving something or someone): a short code check on verbs and item names, plus a cap of ~80 characters.
  Refused gestures are rejections like any other, so villagers see why.
- Witnesses remember gestures like anything else they saw; they decide what a gesture means.
- Shown in both feeds and as a small animation cue in 3D.

### B. A few new real actions, built from engine pieces
Each one is code with a clear right answer, checked like today's actions:
1. **search** a place: a look that also lists items that are present but tucked away (new `hidden` flag).
2. **hide** a held item here: drop it with `hidden` set; only a search or the hider sees it afterwards.
3. **follow** someone: move to where they go next, if you can see them leave and the way is open.
4. **lock / unlock** a door you hold the key to (only where the scenario gives a key).
Villagers keep the right to never use them (week 12 B: items were barely used; that is a finding, not a bug).

### C. Talk limits (week 12 option C)
- A shorter or longer message cap, measured both ways on the Victor benchmark. Needs a rules check
  because it changes the prompt's limit line, nothing else.
- Group talk: today talk needs one person as target (everyone present still overhears). Allow a null
  target meaning "everyone here", as `show` already does. The prompt states the option plainly,
  without suggesting when to use it.

## Not in this week
- The model deciding outcomes ("I pick the lock" judged by a model): breaks the main rule and determinism.
- Week 14 E2 (uncensored model): skipped, nothing to fix (see #104). Revisit only if play shows refusals.
- Open world (#102), backlog #108-#118.

## Checks
- VERIFY.md after A and B: determinism with gestures and the new actions on the stub agent; old
  scenarios unchanged when nobody uses them; save/load keeps `hidden` and locks.
- Unit tests: every refused gesture pattern; hidden items never appear in a plain look or any prompt of
  someone who did not see them hidden or search; follow fails when the target is out of sight.
- Live: Victor benchmark, seeds 1-2 x 5 (the #90 count), against w12n. Report how often villagers use each
  new action, invented-object talk (#83 words), Right person and Decisive. Not worse beyond noise = keep.
- Donovan plays once and says whether the village feels more alive.

## Open questions for you
1. A, B and C all, or A and B first (my suggestion), with C as its own measured week?
2. In B, which of the four actions? My order: hide + search together, then follow, then locks.
3. Gestures in the player's action bar too, or villagers only for now?
