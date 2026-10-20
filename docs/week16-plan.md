# Week 16 plan (approved 2026-10-20: A + D first): more things villagers can do

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
  moving something or someone): a short code check on verbs and item names, plus a cap of 120 characters (80 at first; raised 2026-10-21 after live runs).
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

### D. Villagers make their own actions, checked and merged live (approved)
Like a pull request: a villager writes a new action, the engine runs the checks, and if all pass the
action exists from then on. Same turn: one reply can make an action and use it at once. The checks are
plain code (milliseconds), so nobody waits for another reply.
1. **Format, not free code.** `make` with: a name; parameters (item, person, exit); `needs` from a fixed
   list (holds item, item here, item hidden here, person here, at place); `does` from a fixed list of
   physical effects (put a held item here, hide a held item here, reveal hidden items here, take an item
   here, move self through an exit). Nothing else is accepted.
2. **Checks (the CI).** Valid format; every piece from the lists; a dry run on a copy of the world must
   succeed; afterwards nothing was created or destroyed, nobody but the maker moved, nobody died or was
   held or released, no secret field changed, and the only changes are the ones the action declares.
3. **Merge.** A passing action is logged as a `make` event, so replays rebuild it identically. It is the
   maker's own action from then on (shared with others later, if wanted). A failing one is a rejection
   with the reason, like any other.
4. **Hidden items** come with D: a hidden item is left out of every look, prompt, narrator line and page
   for anyone who did not hide it or reveal it.
5. **Wish list.** Unknown actions a villager tries are saved with what it wanted (sidecar, not the event
   log), so we can see which new physics (locks, fire) villagers reach for. A person decides those.
6. **Prompt.** The action list gains `make` and the villager's own made actions, described plainly,
   never suggesting when or why to make one.
Villagers only in this first build; the player gets it once the format has been seen in play.

## Not in this week
- The model deciding outcomes ("I pick the lock" judged by a model): breaks the main rule and determinism.
- Week 14 E2 (uncensored model): skipped, nothing to fix (see #104). Revisit only if play shows refusals.
- Open world (#102), backlog #108-#118.

## Checks
- VERIFY.md after A and D: determinism with gestures and made actions on the stub agent; old
  scenarios unchanged when nobody uses them; save/load keeps `hidden` and made actions.
- Unit tests: every refused gesture pattern; hidden items never appear in a plain look or any prompt of
  someone who did not hide or reveal them; every CI check refuses a crafted bad action.
- Live: Victor benchmark, seeds 1-2 x 5 (the #90 count), against w12n. Report how often villagers use each
  new action, invented-object talk (#83 words), Right person and Decisive. Not worse beyond noise = keep.
- Donovan plays once and says whether the village feels more alive.

## Order and answers (2026-10-20)
- Build A and D first. B's hide and search come through D (villagers can make them); follow and locks
  wait for the wish list. C is its own measured week.
- Gestures and made actions are for villagers only in this build.

## A + D implementation

The engine interface and visibility rules are documented in [week16-actions.md](week16-actions.md).
The original event snapshot is unchanged. Live benchmark runs and Donovan's play session remain open.

## Fix after the first live runs (2026-10-21)
The first check batch (data/w16a-*, stopped after 3 runs) showed villagers almost stopped talking (106 talk
lines in a run vs about 1,200) and a quarter of actions were refused. Cause: models put gestures in
`message` (talk's field), so nearly all were "empty"; many gestures were speech; checks were too strict
("hands" read as handing over, any item named even when in view). Fixed: gestures read `message`,
gestures with words are refused ("use talk"), items in view may be named, raw ids are refused, the cap is
120 characters. A short live game after the fix: talk back to normal, 9% refused, mostly over-long gestures
before the cap change. The check batch reruns as data/w16b-*.
