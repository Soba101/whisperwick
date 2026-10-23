# Week 17 plan (approved 2026-10-21: B only in generated crimes, secrets words only, A first): roles in 3D, and villagers with lives of their own

Rules carry over: the world is physics only; villagers decide what they believe, want and do;
no director, no formulas deciding opinions, no hints in prompts. Hal's arrests stay his own.
Playtesters are coming in this week (invites, come-back-later, Report this moment are live), so A is
about their first minute and B is about what they find once they look around.

## A. Choose your role in 3D
Today a new player always lands on the 2D page to pick a role, then jumps to 3D.
- `/3d` without a game shows the 3D village behind a small "Choose your role" card: role, crime
  (random or a number) and Start the day. It posts to the same `/newgame` as the 2D page.
- After Start the day the card closes and the game runs in 3D; the How to play guide opens once.
- The 2D page keeps its own picker. Nothing in the engine changes.
- Check: route tests (no game shows the card, a game shows the village), and a play-through in the
  browser at phone and desktop width.

## B. Villagers with their own lives (#118), generated crimes only
Each villager gets three more starting facts, drawn by the crime generator from new pools, seeded by
the crime number like everything else. They are the villager's own memories, like the week 14 grudge
and wish; nothing tells them to use them.
1. **A routine:** where they usually are through the day ("You usually open the forge at 08:00 and eat
   at the Inn at 19:00"). A habit, not a schedule the engine enforces: they decide each turn.
2. **A worry:** something on their mind that is not the murder (a debt, a sick parent, a failing crop).
3. **A private secret unrelated to the murder** (an affair, a small theft, a lie about their past), so
   innocents also have something to hide. Checked by code: it never names the victim, the weapon, the
   murder place or hour, or the killer's motive.
- The fixed Victor scenario stays exactly as it is, so the benchmark is untouched.
- Villagers remembering the player (#118 item 3) waits: it needs trust measures first.
- Check: generator tests (1,000 crimes: every villager gets all three, secrets never touch the crime,
  same number same facts); live: crimes 1-10, one run each, against #109 (8/10 right, 5/10 decisive),
  plus talk per run, quiet hours (Stalls) and invented-object talk (#83).

## Not in this week
- Gestures stay off (#122). Talk limits (old C). Live talk speed check (#106) runs when the PC is free.

## Open questions for you
1. B only in generated crimes, leaving the Victor benchmark alone? (My suggestion: yes.)
2. Should a secret ever have a physical trace (a hidden letter, a stolen coin)? (My suggestion: not yet;
   words only this week, items later if play shows it would help.)
3. A first, then B? (My suggestion: yes, A is small and helps the playtesters now.)

## Results: live check on generated crimes, week 17 B (2026-10-22, #123)
Crimes 1-10, one run each, `none` player, memory on, 3 days, main at 92fcda0 (data/w17c/, eval in data/w17c/eval.txt). Same crime numbers as #109, so the murder facts are identical; only the villagers' routines, worries and secrets are new.

| Crime | Killer | #109 Hal holds | Week 17 Hal holds | GuardStall h | Talk lines (#109 / now) |
|---|---|---|---|---:|---|
| 1 | Bob | Bob (right) | Victor, Bob (mixed) | 2 | 193 / 1,063 |
| 2 | Alice | Alice (right) | Alice (right) | 2 | 1,508 / 1,167 |
| 3 | Bob | Bob (right) | nobody | 24 | 248 / 224 |
| 4 | Bob | Bob (right) | Mayor (wrong) | 14 | 522 / 514 |
| 5 | Mayor | Bob (wrong) | Mayor (right) | 8 | 2,323 / 912 |
| 6 | Mayor | Mayor (right) | Mayor (right) | 0 | 271 / 299 |
| 7 | Sarah | nobody | nobody | 48 | 79 / 311 |
| 8 | Bob | Bob (right) | Mayor (wrong) | 24 | 1,694 / 2,299 |
| 9 | Victor | Victor (right) | Victor (right) | 1 | 1,215 / 2,142 |
| 10 | Mayor | Mayor (right) | Mayor (right) | 0 | 645 / 654 |

- Right person 5/10 (plus 1 mixed) against 8/10 in #109; Fisher p = 0.35, so not beyond noise with one run per crime. Decisive 5/10, same as #109.
- Wrong holds rose from 1 to 2, and both new ones are the Mayor while Bob was the killer (crimes 4 and 8).
- Crime 8 churned: 11 arrests and 10 releases.
- Rejected actions rose from 3.4% to 5.9% per run (mean). Quiet hours (Stalls) are unchanged: 14 in both batches. Talk per run: 870 in #109, 959 now.
- Accomplices are still never held.
- Not measured: invented-object talk (#83); there is no counting script yet. Also not checked: whether villagers ever mention their worries or secrets.

## Seed 2 bisect, step 1: week 13 merge c3fd849 (#126)

- Right person 3/5 (Victor in r1, r3, r4; nobody in r2 and r5). No wrong holds.
- Week 12 code: 13/15. Weeks 13-15: 7/15. Fisher p = 0.25 against week 12 and 1.0 against weeks 13-15.
- Not decisive: 3/5 sits between the two. The week 13 merge may lose some, but five runs cannot show it.
- Next step needs a choice: more runs at c3fd849, or test 2eab616 (use action) or 6bf30d5 (everyday items).
