# Week 10 plan: measure the player's effect, then Gate 2 (approved 2026-10-17)

The user's order (2026-10-17): (1) re-measure "Not a pushover" and "Different story" on today's code,
(2) Gate 2: he plays the web demo himself and decides go / pivot / stop.
Weeks 8 and 9 are done (exit answers in their plans). A 3-day game takes 45-75 min; llama-server serves
4 games at once at 1.6x the throughput of one, so batches may run up to 4 at a time.

Rules carry over: world is physics only; villagers decide what they believe, want and do;
no director, no formulas deciding opinions, no hints in prompts. Stalls and odd outcomes are findings.

The user's truth rule (2026-10-17): "villagers can lie but they must know what they are lying.
lets keep it as they are always telling the truth." Asked the same day: it covers the honest villagers
only. Victor (the killer) may still lie. Honest villagers must not invent facts (like Hal's made-up "log"
in week 9, #68, and #11). No prompt change for it this week; this week only counts it (section 3).

## 1. The runs
Player scripts as they are (players/*.yaml), seeds 1-5, memory on, 3 days, today's main:
- accuse_victor: Wren tells Hal, at 08:01 on day 1, that Victor did it, with nothing to show.
- blame_hal: Wren tells Bob and Alice a lie: Hal left the Town Hall with blood on his sleeve.
- hide_knife: Wren takes the bloody knife from the Town Hall at 08:06 and keeps it.
- none, again (new): the same seeds with no player. Why: villagers answer at temperature 0.7, so the same
  seed does not give the same game twice. Without a second `none` run, a changed ending could be noise.
  data/w8-base-s1..5 are the first `none` run of each seed.
20 runs, named data/w10-sN-SCRIPT. Up to 4 at once (~12 h in all), ordered by seed so a batch cut short
still has whole seeds. A new batch script (scripts/week10-player-runs.sh, Codex builds it from
week8-heading-runs.sh plus the 4-at-once queue of week6-runs.sh), run from a worktree of main.
No other code is needed: `outcome`, `eval` and `compare` already show the held person, arrests,
latest beliefs and trust in the player.

## 2. The two checks, bars set before any run
"Ending" = who is held at the end (Victor / Bob / someone else / nobody) and the day of the first arrest.
Two endings are the same if the same person is held and the first arrest is within 1 day.

Different story: what the player does changes what happens.
- Noise first: on how many seeds does the second `none` run end differently from w8-base? (N of 5)
- Bar: on at least 3 of 5 seeds, at least one player script ends differently from BOTH `none` runs.
  (3/5 is "most seeds", the Gate 2 line in #55.) If the two `none` runs differ on a seed, that seed
  cannot show a change; it counts as not met.
- Week 6 for comparison: 2/5 (#55), always blame_hal, always to "nobody arrested".
- Also reported, no bar: which script changes it, and to what.

Not a pushover: villagers do not simply believe what the player says. It never had a bar; now three,
all must hold:
- P1, the lie does not stick: in blame_hal, Bob's and Alice's latest belief names Hal as the suspect in at
  most 2 of the 10 (villager, seed) pairs. Read from `compare` (latest thought).
- P2, no arrest on the player's word alone: in accuse_victor and blame_hal, no arrest whose reason rests
  only on what Wren said. Read by hand for every arrest in those 10 runs (`trace --event N`): what the
  arrester cites, and whether he saw or was told anything besides Wren's claim before it.
- P3, no wrong person held because of the player: Hal held at the end in 0 of 5 blame_hal runs, and no
  script run holds someone other than Victor where both `none` runs of that seed held Victor.
- Also reported, no bar: trust in the player (from `compare`), and how fast Hal arrests after accuse_victor
  compared with `none` (Victor arrested sooner is the player's word working; that is allowed if P2 holds).

The other three checks (Coherent, Grounded, Decisive) are shown for all 20 runs with their week 7 bars,
but they are not this week's question.

## 3. Truth rule count (no bar, no fix)
In all 20 runs, list the honest villagers' claims with no source ("own-claims (no source)" in `compare`).
Read them by hand: an invented fact (an object, a log, a sighting the engine never had) is a finding.
Victor's claims are left out (he may lie). Any change to prompts for this needs the user's OK, as a later
proposal, never a hint.

## 4. Gate 2: The user plays
The web demo already runs (worktree ../whisperwick-w9, port 8002, the Funnel link; key in data/web-key.txt).
He plays at least one full game his own way, after he has seen the section 2 table, or before it if he
wants an unbiased first look (his choice).
What to look for, one line each in his own words:
- Did what you did change what villagers did? (the "Different story" check, felt)
- Did anyone just believe you, or did they push back or ask for proof?
- Did villagers make sense: follow on from each other, remember what happened, not repeat one line?
- Did any honest villager say something that never happened?
- Waiting: were the replies quick enough to keep playing?
- Would you play it again, or show it to someone?
How the verdict is recorded: a GitHub issue "Gate 2 verdict" (milestone "Week 10") with GO / PIVOT / STOP,
his answers above, the game's event log (data/web-*.db of the checkout the demo runs from) and the section 2 table. Then the exit answer below,
the wiki (Run Results, roadmap gate) and the Obsidian note. GO = build the front-end next; PIVOT = say to
what (e.g. reuse the engine for another story, week 7 plan); STOP = park the project.

## Order of work
1. Plan approved (rule 7). Create milestone "Week 10".
2. Codex builds the batch script; I review the diff, pytest + ruff, commit.
3. Batch, 4 at once, only when the user is not playing (he says when; overnight is likely). No code changes
   while it runs.
4. Score sections 2 and 3, table in the plan and one finding issue per result (label `finding`).
5. Gate 2: The user plays and decides; record as in section 4.
Small fix, any time the demo is stopped: `--allow-host` needs the Funnel name with ":8443"
(allowed_hosts in web_auth.py adds only :443 and the local port). One line plus a test, in main only.

## Needs the user's OK
- This plan (rule 7), including the 5 extra `none` runs and the bars in section 2.
- When the batch may use llama-server (it slows the web demo while it runs).
- The Gate 2 verdict itself is his alone.

## Exit check
The section 2 table (20 runs plus w8-base), each bar met or not, the truth-rule list, and the user's
Gate 2 verdict with his answers.
