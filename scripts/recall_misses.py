"""Measure whether villagers' recall misses memories today (#71, step 1). No model calls.

For each saved recall: rebuild the villager's memory stream at that tick (exact replay,
no model), rerun the search, then look at what the villager did next: the action it took
in the same turn and the memories its next thought cited. A cited memory the search did
NOT return is a candidate miss. We sort those into:
  cut     - shares a word with the search, but five others ranked higher (top-5 cut-off)
  meaning - shares no word, but does share meaning (a stem, a name for the same person,
            or a near word from the small list below). This is what meaning search would fix.
  id      - the search words named this memory by id (m12); ids are never searched
  other   - nothing in common with the search: cited for some other reason, not a miss
The near-word list is ours and small on purpose: it only measures, it never reaches a prompt.

Usage: uv run python scripts/recall_misses.py data/w8-base-s1.db ... [--dump FILE]
"""

import json
import re
import sys
from collections import Counter

from whisperwick import screen_replay
from whisperwick.memory import MemoryStream, words
from whisperwick.recall import search

# Same person or thing, other words (names from the scenario; occupations are public).
NEAR = [
    {"victor", "merchant"}, {"hal", "guard"}, {"sarah", "priest"}, {"bob", "blacksmith"},
    {"alice", "innkeeper"}, {"wren", "newcomer", "stranger", "player"},
    {"mayor", "aldric"}, {"knife", "blade", "dagger", "weapon"},
    {"mud", "muddy", "loam", "clay", "soil", "dirt"}, {"boots", "boot", "shoes"},
    {"kill", "killed", "killing", "murder", "murdered", "stab", "stabbed", "dead", "death", "body"},
    {"seal", "mark", "crest"}, {"inn", "tavern"}, {"temple", "shrine"},
]


def stem(w: str) -> str:
    """A crude stem, enough to join 'boots'/'boot' and 'stabbed'/'stab'."""
    for end in ("ing", "ed", "es", "s"):
        if w.endswith(end) and len(w) - len(end) >= 3:
            return w[: -len(end)]
    return w


def meaning(text: str) -> set[str]:
    """Words widened by stems and the near-word list. Used only to judge, never to search."""
    out = set()
    for w in words(text):
        out |= {w, stem(w)}
        for group in NEAR:
            if w in group or stem(w) in group:
                out |= group | {stem(g) for g in group}
    return out


def kind_of_miss(query: str, text: str, mid: str) -> str:
    if mid in re.findall(r"\bm\d+\b", query.lower()):
        return "id"
    if words(text) & words(query):
        return "cut"
    if meaning(text) & meaning(query):
        return "meaning"
    return "other"


def stream_at(full: MemoryStream, tick: int, query: str, saved: list[str]) -> MemoryStream:
    """The stream as it was at the recall (streams only append, so it is a prefix).

    Memories made in the same minute may come before or after the recall, so we take
    the shortest prefix whose search gives exactly the saved result.
    """
    before = sum(m.tick < tick for m in full.memories)
    upto = sum(m.tick <= tick for m in full.memories)
    s = MemoryStream()
    for n in range(before, upto + 1):
        s.memories = full.memories[:n]
        if [mid for mid, _ in search(s, query)] == saved:
            return s
    return s  # no exact match: counted as not rebuilt below


def analyse(db: str, dump: list) -> Counter:
    source, c = screen_replay.replay(db)
    c.world.log.db.close()
    count = Counter()
    for r in source.recalls:
        if r.get("kind") != "recall":
            continue
        npc, tick, query = r["npc"], r["tick"], r["words"]
        stream = stream_at(c.memories[npc], tick, query, r["found"])
        found = [mid for mid, _ in search(stream, query)]
        count["recalls"] += 1
        count["rebuilt_same"] += found == r["found"]
        count["found_nothing"] += not r["found"]
        count["id_in_words"] += bool(re.search(r"\bm\d+\b", query.lower()))
        # Same turn: what it did after reading the results (an act recall).
        acts = [e for e in source.events if e.actor == npc and e.tick == tick]
        # Next thought: the first belief record of this villager at or after the recall.
        nxt = next((b for b in source.beliefs if b["npc"] == npc and b["tick"] >= tick), None)
        cited = [b["memory_id"] for b in (nxt or {}).get("because", []) if b.get("memory_id")]
        misses = []
        for mid in dict.fromkeys(cited):
            i = int(mid[1:]) if re.fullmatch(r"m\d+", mid) else -1
            if mid in r["found"] or not 0 <= i < len(stream.memories):
                continue
            k = kind_of_miss(query, stream.memories[i].text, mid)
            misses.append((k, mid, stream.memories[i].text))
        kinds = {k for k, _, _ in misses}
        for k in ("cut", "meaning", "id"):
            count[f"recalls_with_{k}"] += k in kinds
        count["recalls_with_any_miss"] += bool(kinds - {"other"})
        # Upper bound: memories the search never sees but that share meaning with the words.
        unseen = [m for m in stream.memories
                  if not words(m.text) & words(query) and meaning(m.text) & meaning(query)]
        count["recalls_with_unseen_meaning"] += bool(unseen)
        dump.append({
            "run": db, "npc": npc, "tick": tick, "words": query, "stream": len(stream.memories),
            "found": [(mid, stream.memories[int(mid[1:])].text) for mid in r["found"]],
            "acts": [{"type": e.type, "data": e.data} for e in acts],
            "next_thought": (nxt or {}).get("thoughts", "")[:400], "cited": cited,
            "misses": misses, "unseen_meaning": len(unseen),
        })
    return count


def main(args: list[str]) -> None:
    dump_path = None
    if "--dump" in args:
        dump_path = args[args.index("--dump") + 1]
        args = [a for a in args if a not in ("--dump", dump_path)]
    dump: list = []
    total = Counter()
    cols = ("recalls", "rebuilt_same", "found_nothing", "id_in_words", "recalls_with_cut",
            "recalls_with_meaning", "recalls_with_id", "recalls_with_any_miss",
            "recalls_with_unseen_meaning")
    print("run\t" + "\t".join(c.replace("recalls_with_", "") for c in cols))
    for db in args:
        n = analyse(db, dump)
        total += n
        print(db.split("/")[-1] + "\t" + "\t".join(str(n[c]) for c in cols))
    print("TOTAL\t" + "\t".join(str(total[c]) for c in cols))
    if dump_path:
        with open(dump_path, "w") as f:
            json.dump(dump, f, indent=1)


if __name__ == "__main__":
    # Self-check of the judge: a knife/blade pair is a meaning miss, not a cut-off.
    assert kind_of_miss("the blade", "a bloody knife", "m3") == "meaning"
    assert kind_of_miss("knife m3", "a bloody knife", "m3") == "id"
    main(sys.argv[1:])
