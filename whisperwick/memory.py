"""Memory stream for each NPC, in the style of the Generative Agents paper.

This lives on the agent side. It is NOT part of World state and never
touches state_hash. The world stays the truth; this is what an NPC *believes*.
"""

import re
from collections import UserDict
from dataclasses import dataclass

from whisperwick.events import Event
from whisperwick.memory_text import (  # noqa: F401 (re-exported)
    describe,
    importance_of,
    look_text,
    name_of,
)
from whisperwick.player import PLAYER_ID
from whisperwick.world import World

# Each game minute makes a memory a little less recent.
RECENCY_DECAY = 0.995


@dataclass
class Memory:
    tick: int  # game minute it was stored
    text: str
    importance: int  # 1 (trivial) to 10 (life changing)
    kind: str = "observation"  # "observation" | "reflection" | "evidence"
    # The world event behind this memory. None for evidence and looks: they are not events.
    # A belief that cites this memory can then be traced back to what really happened.
    event_id: int | None = None


def memory_id(index: int) -> str:
    """The id a belief uses to cite a memory: its place in the stream, e.g. 'm12'.

    Streams are append-only, so a memory's index never changes and the id stays stable.
    """
    return f"m{index}"


def words(text: str) -> set[str]:
    """Lowercase words of 3+ letters. Ids like npc_victor split into npc and victor."""
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 3}


class MemoryStream:
    """Everything one NPC remembers, in the order it was stored."""

    def __init__(self):
        self.memories: list[Memory] = []

    def add(
        self,
        tick: int,
        text: str,
        importance: int,
        kind: str = "observation",
        event_id: int | None = None,
    ) -> Memory:
        memory = Memory(tick, text, importance, kind, event_id)
        self.memories.append(memory)
        return memory

    def score(self, memory: Memory, now_tick: int, query_words: set[str]) -> float:
        """Recency + importance + relevance. Each part is 0..1, equal weights."""
        recency = RECENCY_DECAY ** max(0, now_tick - memory.tick)
        importance = memory.importance / 10
        # An empty query matches nothing, so relevance is 0 (and we never divide by 0).
        relevance = len(words(memory.text) & query_words) / len(query_words) if query_words else 0
        return recency + importance + relevance

    def retrieve(self, now_tick: int, query: str, k: int = 8) -> list[Memory]:
        """The k best memories, oldest first, so a prompt reads like a story."""
        query_words = words(query)
        # Ties go to the newer tick, then to the later one stored. Fully deterministic.
        ranked = sorted(
            enumerate(self.memories),
            key=lambda pair: (self.score(pair[1], now_tick, query_words), pair[1].tick, pair[0]),
            reverse=True,
        )
        best = sorted(ranked[:k], key=lambda pair: (pair[1].tick, pair[0]))
        return [memory for _, memory in best]


class Memories(UserDict):
    """One MemoryStream per NPC id, made on first use."""

    def __missing__(self, npc_id: str) -> MemoryStream:
        self[npc_id] = MemoryStream()
        return self[npc_id]

    def observe(self, event: Event, world: World) -> None:
        """Give the event to everyone who saw it, and to the actor (it knows what it did).

        Call this right after the event, before anyone else moves.
        describe() reads where each witness is *now* to word a move as arrive or leave.
        """
        for npc_id in sorted({*event.witnesses, event.actor}):
            # The player is a human, not a code agent: no memory stream for them.
            if npc_id == PLAYER_ID:
                continue
            line = describe(event, world, npc_id)
            # Keep the event id, so a later belief can point back at this exact event.
            self[npc_id].add(event.tick, line, importance_of(event, npc_id), event_id=event.id)

    def observe_look(
        self, npc_id: str, observation: dict, tick: int, world: World | None = None
    ) -> None:
        """Remember what a look showed. Cheap and low importance (1)."""
        if npc_id == PLAYER_ID:
            return  # the player has no memory stream
        # The wording lives in memory_text.look_text: one sentence per fact, so a body
        # is never listed next to a living person's name (#49).
        line = look_text(observation, tick, world)
        # Seeing a body matters far more than seeing who is around.
        # .get() keeps older observations (made before bodies existed) working.
        bodies = observation.get("bodies") or []
        importance = 7 if bodies else 1
        # Items on the ground matter a little more (a knife by a body is a clue).
        if observation.get("items"):
            importance = max(importance, 5)
        self[npc_id].add(tick, line, importance)


def seed_evidence(memories: Memories, evidence: dict[str, list[str]], tick: int) -> None:
    """Give each NPC its private starting memories. Very important (9), kind "evidence".

    Sorted by npc id so the order of memories is the same every run.
    """
    for npc_id in sorted(evidence):
        for line in evidence[npc_id]:
            memories[npc_id].add(tick, line, 9, "evidence")
