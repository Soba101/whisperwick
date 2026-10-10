"""Recall: a villager searches its own memories, by its own choice.

The code only searches (shared words) and shows what it found. It never picks what to
remember for the villager. Agent side only: never world state, never an event.
"""

from typing import NamedTuple

from whisperwick.agent_log import AgentLog
from whisperwick.memory import Memory, MemoryStream, memory_id, words
from whisperwick.notebook import Notebooks

RECALL_MAX = 5  # how many matches come back at most
RECALL_WORDS_MAX = 100  # the search words are a few words, never an essay


class Private(NamedTuple):
    """One run's private agent-side memory tools. None anywhere means memory is off."""

    stream: MemoryStream
    notebooks: Notebooks
    log: AgentLog


class Recall(NamedTuple):
    """What a villager asked to search for, instead of acting. Not an Intent."""

    words: str


def search(stream: MemoryStream, query: str) -> list[tuple[str, Memory]]:
    """Top matches over ALL kinds, oldest first. Score = number of shared words.

    Ties go to the newer memory (later index). Nothing shared = nothing found.
    """
    wanted = words(query)
    scored = [
        (len(words(m.text) & wanted), i, m) for i, m in enumerate(stream.memories)
    ]
    hits = sorted((s for s in scored if s[0] >= 1), key=lambda s: (s[0], s[1]), reverse=True)
    best = sorted(hits[:RECALL_MAX], key=lambda s: s[1])
    return [(memory_id(i), m) for _, i, m in best]


def clean_words(raw) -> str:
    """The search words as one trimmed line (the model may send None or newlines)."""
    return " ".join(str(raw or "").split())[:RECALL_WORDS_MAX]


def act_lines(query: str, found: list[tuple[str, Memory]]) -> list[str]:
    """Plain lines shown on the second ask of a turn."""
    if not found:
        return [f'You searched your memory for "{query}" and remember nothing about it.']
    head = f'You searched your memory for "{query}" and remember:'
    return [head, *(f"- {m.text}" for _, m in found)]
