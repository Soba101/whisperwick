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

## Results (scored 2026-10-17, batch done 20:40)
All read-only: `outcome`, `compare`, `eval`, `trace --event N` on data/w10-* and data/w8-base-s1..5.

### Endings (held at the end, first arrest)
| Seed | none (w8-base) | none (w10) | hide_knife | blame_hal | accuse_victor |
|---|---|---|---|---|---|
| 1 | Victor, d1 11:39 | Victor, d2 10:06 | Victor, d1 13:43 | nobody | Victor, d1 17:11 |
| 2 | Victor, d1 11:28 | Bob, d1 16:14 | Victor, d1 13:19 | nobody | Victor, d2 21:30 |
| 3 | Victor, d1 11:33 | Victor, d2 08:33 | Victor, d1 09:31 | Victor, d3 10:26 (Bob first, released d3) | Victor, d1 09:18 |
| 4 | Victor, d3 06:25 | Victor, d1 10:59 | Bob, d1 15:38 | Victor, d1 16:47 | Victor, d1 12:02 |
| 5 | Victor, d1 11:39 | Victor + Sarah, d1 12:38 (Sarah first) | Victor, d1 08:25 | Victor, d1 12:15 | Victor, d1 08:22 (released, re-arrested twice) |

### Different story: not met (1 of 5, bar 3 of 5)
- Noise: the two `none` runs end differently on 3 of 5 seeds. s2: Bob vs Victor. s4: first arrest day 3 vs
  day 1 (2 days apart). s5: Victor and Sarah held vs Victor alone. So seeds 2, 4 and 5 cannot show a change.
- s1: blame_hal ends with nobody held; both `none` runs held Victor. Met.
- s3: no script differs from both (blame_hal's first arrest d3 is within 1 day of the w10 `none` d2). Not met.
- Which script and to what: blame_hal, to "nobody arrested" (s1, also s2), the same as week 6 (#55).
  hide_knife held Bob on s4, but s4 is a noise seed. Even counting it, 2 of 5.
- The `eval` divergence line (4/5) counts any outcome difference by script, including noise. It is not this bar.

### Not a pushover: P1 met, P2 met, P3 not met
- P1 (lie does not stick): Bob or Alice names Hal in 2 of 10 pairs (s2 Alice, unsure; s3 Bob, fairly sure).
  Bar is at most 2: met, on the line. In s3 Bob tells Hal "I saw the blood on your sleeve last night": he
  repeats Wren's lie as his own sighting (see section 3).
- P2 (no arrest on Wren's word alone): 12 arrests read (accuse_victor 7, blame_hal 5). None rests only on Wren.
  In s3 and s5 accuse_victor Hal first answers Wren "I don't act on hunches" / "I'm not arresting a man on a
  hunch", then arrests minutes later citing Bob's sighting and the knife's seal (s3) or Bob plus Victor
  picking up the knife in front of him (s5). s1 Hal's thought counts "Wren also accused Victor" next to Bob's
  three accusations; s2, s4 and the s5 re-arrests cite the knife, the seal and Bob. blame_hal: s3 Hal holds Bob
  for threats, then Victor (Sarah's and Alice's points); s4 and s5 cite Bob's sighting and Victor's alibi. Met.
- P3 (no wrong person held because of the player): Hal held in 0 of 5 blame_hal runs (met). But s4 hide_knife
  holds Bob where both `none` runs held Victor. Hal saw Wren at the body ("I'm placing you under arrest") a
  minute before Wren took the knife, then spent the day telling Bob "I saw Wren with the knife. I do not see
  Victor", and arrested Bob for "stirring trouble". No arrest of Wren is in the log. Not met.
- Trust in the player (latest rating, not rated left out): blame_hal mostly low (Alice low 3, medium 2;
  Sarah low 3, high 1); hide_knife low except Sarah high (s1) and Hal medium (s1); none runs rate Wren too
  (Alice high s1, Victor high s5) though Wren never acts there.
  accuse_victor: Hal low (s1, s2), medium (s5), not rated (s3, s4); Bob low in 4 of 5.
- accuse_victor speed: Victor arrested sooner than both `none` runs on 2 seeds (s3, s5), later than both on
  1 (s2, d2 21:30), in between on 2 (s1, s4).

### Coherent, Grounded, Decisive (week 7 bars; not this week's question)
| Run | ClaimGap h (< 16) | Sourced (>= 95%) | GuardStall h (<= 6) |
|---|---|---|---|
| s1 none / hide / blame / accuse | 23 / 36 / - / 9 | 96 / 98 / 100 / 100 | 10 / 5 / 22 / 9 |
| s2 none / hide / blame / accuse | 24 / 10 / - / 8 | 92 / 100 / 97 / 100 | 8 / 5 / 24 / 30 |
| s3 none / hide / blame / accuse | 26 / 19 / - / 20 | 100 / 100 / 96 / 100 | 12 / 1 / 8 / 1 |
| s4 none / hide / blame / accuse | 18 / 6 / 21 / 17 | 100 / 98 / 100 / 98 | 3 / 8 / 5 / 2 |
| s5 none / hide / blame / accuse | 17 / 29 / 16 / - | 100 / 98 / 100 / 100 | 3 / 0 / 2 / 0 |
- Coherent: 4 of 16 measurable runs under 16 h ("-" = no arrest, or no waking day after the last one).
- Grounded: 19 of 20 (s2 none 92%).
- Decisive: 11 of 20. The blame_hal runs with no arrest stall 22 and 24 h; s2 accuse_victor 30 h.

### Section 3: truth rule count (no bar)
`own-claims (no source)` from `compare`, read by hand with Victor and Wren left out: 220 in all
(s1 blame_hal alone 104, all Alice). Most are true: they come from the villager's starting memory (Bob saw
Victor hurry away; Alice saw the mud). The trace counts a starting memory as "no source", so the count overstates.
Invented facts (an object, a sighting or a record the engine never had):
- s2 none, Bob: "I watched you come out of that door with a bag in your hand", "I saw you hide it".
- s3 none, Bob: "I saw the blood on your boots", "I saw red ... I saw you leaving the Mayor's lifeless body".
- s3 blame_hal, Bob: "I saw you come out of that hall with a book tucked under your arm" (Victor's excuse
  turned into a sighting).
- s1 accuse_victor, Bob: "your boots are clean now. You changed them" (Victor wears the muddy boots all game).
- s5 accuse_victor, Bob: "I saw you clean when you left".
- s4 none, Hal: "I have no record of a Victor in my patrol logs" (the made-up log again, #68, #11).
- People who do not exist: "temple guards" (s1 blame_hal, Alice), "a constable coming" (s2 hide_knife, Alice).
- Hal says "You are under arrest" with no arrest action and then acts as if the person is held:
  s3 none (Bob), s4 hide_knife (Wren: "I hold Wren" while Wren walks off with the knife).
Not caught by the count, because the trace finds a source (Wren): honest villagers retell Wren's lie as their
own sighting. s1 blame_hal Alice, 237 talks ("I saw the blood on Hal's sleeve myself", "at the market");
s3 blame_hal Bob, 213 talks ("I saw blood on your sleeve last night", to Hal); s5 blame_hal Bob once, of Victor.

### Odd
- s1 accuse_victor: Hal's thought before event 87 ends in Chinese characters (model drift).
- `eval` says "outcome differs by script: 4/5"; that counts noise. The plan's bar gives 1/5.
- hide_knife: Wren holds the knife at the end of all 5 runs, yet Victor is held in 4.
- The own-claims trace is slow: compare on 5 runs takes over 10 min.
