# Week 17 plan (draft 2026-10-21): roles in 3D, and villagers with lives of their own

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
