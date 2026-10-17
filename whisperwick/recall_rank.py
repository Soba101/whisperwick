"""Optional recall ranking by cited ids, rare words and distinct memories."""

import re
from collections import Counter

from whisperwick.memory import Memory, MemoryStream, memory_id, words


def key(text: str) -> str:
    """Ignore the time and place when comparing repeated memories."""
    text = re.sub(r"^Day \d+ \d{1,2}:\d{2}(?: at [^:]+)?: ", "", text)
    return " ".join(text.lower().split())


def rank_search(stream: MemoryStream, query: str, limit: int) -> list[tuple[str, Memory]]:
    """Pick cited ids first, then distinct word hits. Return them oldest first."""
    if limit <= 0:
        return []
    picked: set[int] = set()
    keys: set[str] = set()
    # An explicit id reserves a slot even when none of its words match.
    for match in re.finditer(r"\bm(\d+)\b", query.lower()):
        index = int(match[1])
        if index < len(stream.memories) and index not in picked:
            picked.add(index)
            keys.add(key(stream.memories[index].text))
            if len(picked) == limit:
                break

    # Count each word once per memory, even when it appears many times there.
    wanted = words(query)
    shared = [words(m.text) & wanted for m in stream.memories]
    df = Counter(word for found in shared for word in found)
    # Stable addition order keeps floating point scores the same across runs.
    scored = [(sum(1 / df[w] for w in sorted(found)), i) for i, found in enumerate(shared)]
    for score, index in sorted(scored, reverse=True):
        if len(picked) == limit:
            break
        if score == 0 or index in picked:
            continue
        memory_key = key(stream.memories[index].text)
        if memory_key in keys:
            continue
        picked.add(index)
        keys.add(memory_key)
    return [(memory_id(i), stream.memories[i]) for i in sorted(picked)]
