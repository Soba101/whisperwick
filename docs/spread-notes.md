# Spread comparison: w12n seeds 1 and 2, repeat 1

Ran `uv run whisperwick spread ../whisperwick/data/w12n-s{1,2}-r1.db SUBJECT`
for both `npc_victor` and `npc_bob` (expand the seed braces). Analysis reads saved
events and beliefs only; it calls no model. Both sidecars name Victor as murderer.

Seed 1 has 503 tagged claims about Victor and 464 about Bob, but no arrest or
release of either. Bob first accuses Victor at e3; Victor first attacks Bob at
e22. Neither line reaches Hal: he witnesses **zero talk events** and never moves
from the Town Hall. All 15 of his saved beliefs have no suspect. His citations
are his initial evidence, looks, and picking up the knife (e1), not the market
claims.

Seed 2 has 942 tagged claims about Victor and 616 about Bob. Hal moves to the
market at e5. Bob's accusation at e6 reaches him; Hal's first belief (b3, after
e29) cites it as m3, alongside e11 and his own words. Before arrest e113, his
latest belief is b8 (after e109): it suspects Victor and cites Bob at e91
(m124), his own accusations e92/e97, Victor's attack on Bob at e93, and initial
evidence. There is no Bob arrest or release of either subject.

**No evidence that one early false claim causes seed 1's failure.** The observed
difference is a missing communication path to Hal. Seed 2 supplies that path;
its arrest belief combines repeated testimony and Hal's interpretation of the
boots. Citations show recorded dependencies, not causal proof.
