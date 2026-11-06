# Week 18 plan (draft, needs Donovan's OK): a detective journal, and a guard round Hal may choose

Rules carry over: the world is physics only. Villagers decide what they believe, want and do.
No director, no formulas deciding opinions, no hints in prompts. Hal's arrests stay his own.

Why these two: playtesters lose track of who said what (#89, #113), and the biggest cause of
failed runs is Hal staying in the Town Hall and hearing too little (#100, #126: 18 of 20
"nobody held" runs on seed 2). The first helps the player, the second is the main gap in
the village itself.

## A. Detective journal (#113), player side only
A "What I know" tab, built by code from the player's own feed. No model call and no new facts.
- Who said what about whom: each line the player heard or saw, grouped by the person it is about.
- Items the player saw, and where and when.
- Places the player visited, with the hours.
- Contradictions: two lines about the same person and hour that name different places. This is
  plain matching of names and hours that already appear in the feed. It never says who is right.
- It shows only what the player's own feed holds, so it can never be a hint.
- Check: unit tests on a fixed feed (grouping, a contradiction found, nothing from outside the
  feed), and a play-through in the browser at phone and desktop width.

## B. A guard round Hal may choose (#114)
Today Hal can only `move` one place at a time, and on bad seeds he never moves. Proposal: a new
action `patrol` for anyone with authority. It takes one hour and walks the four places in turn,
so Hal is a witness at each one for a quarter of the hour. It is listed with his other actions,
like `arrest`. Nothing makes him use it, and no prompt line says he should.
- Engine: `patrol` is a move chain that the engine resolves. It writes one event for each place,
  so witnesses and recall work as they do for a move.
- Open question for you: is a new action in Hal's list a hint? My view is no. It is a physical
  ability, like `arrest`, and he still decides. If you say it is a hint, B is dropped and #114 stays open.
- Check: engine tests (patrol order, witnesses at each stop, same seed gives the same events) and
  verify-world-engine. Live: seed 1 x10 and seed 2 x10, against the pooled rates (seed 2 about
  50-60% right, #126; seed 1 fails because Hal hears no one, #100). Also count how often Hal chooses it.

## C. Close week 17 (#123)
- Rerun of crimes 1-10 at e0eab58 (data/w17d), running now. Pool it with data/w17c, compare with
  #109, then close #123.
- Worry and secret talk (counted 2026-11-06 on data/w17c with marker phrases, rough):
  about 22 of 60 villagers mention their own worry and about 10 of 60 their own secret.
  Secrets come out mostly under pressure (crime 9: the Mayor, held, confesses the exam lie).

## Not in this week
- Day and night (#112): bigger, and it changes the clock and the physics. Later.
- Bring your own API key (#116): needs a hosted model screen and a cost estimate first.
- Gestures stay off (#122).

## Open questions for you
1. A and B both, or A only? (My suggestion: both, A first because it is small.)
2. Is `patrol` a fair physical ability or a hint? (My suggestion: fair.)
3. 10 runs per seed for B is about 15-30 hours of PC time. OK?
