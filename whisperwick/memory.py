"""Memory stream for each NPC, in the style of the Generative Agents paper.

This lives on the agent side. It is NOT part of World state and never
touches state_hash. The world stays the truth; this is what an NPC *believes*.
"""

import re
from collections import UserDict
from dataclasses import dataclass

from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.llm_client import LLMError
from whisperwick.memory_text import describe, importance_of, name_of  # noqa: F401 (re-exported)
from whisperwick.player import PLAYER_ID
from whisperwick.world import World

# Each game minute makes a memory a little less recent.
RECENCY_DECAY = 0.995
REFLECTION_IMPORTANCE = 8
REFLECTION_INPUT = 30  # how many recent memories a reflection reads
REFLECTION_MAX_CHARS = 400  # a reflection is a few sentences, never an essay


@dataclass
class Memory:
    tick: int  # game minute it was stored
    text: str
    importance: int  # 1 (trivial) to 10 (life changing)
    kind: str = "observation"  # "observation" | "reflection" | "evidence"


def words(text: str) -> set[str]:
    """Lowercase words of 3+ letters. Ids like npc_victor split into npc and victor."""
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 3}


class MemoryStream:
    """Everything one NPC remembers, in the order it was stored."""

    def __init__(self):
        self.memories: list[Memory] = []

    def add(self, tick: int, text: str, importance: int, kind: str = "observation") -> Memory:
        memory = Memory(tick, text, importance, kind)
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
            self[npc_id].add(event.tick, line, importance_of(event, npc_id))

    def observe_look(
        self, npc_id: str, observation: dict, tick: int, world: World | None = None
    ) -> None:
        """Remember what a look showed. Cheap and low importance (1)."""
        if npc_id == PLAYER_ID:
            return  # the player has no memory stream
        people = ", ".join(observation["people"]) or "nobody"
        when = Clock(tick).label().capitalize()
        line = f"{when} at {observation['location']}: you looked around and saw {people}"
        # Seeing a body matters far more than seeing who is around.
        # .get() keeps older observations (made before bodies existed) working.
        bodies = observation.get("bodies") or []
        if bodies:
            line += f". Dead here: {', '.join(bodies)}"
        importance = 7 if bodies else 1
        # Items on the ground matter a little more (a knife by a body is a clue).
        # The observation holds ids; the world gives the names for the memory text.
        items = observation.get("items") or []
        if items:
            names = [f"{world.items[i].name} ({i})" if world and i in world.items else i
                     for i in items]  # fmt: skip
            line += f". On the ground: {', '.join(names)}"
            importance = max(importance, 5)
        self[npc_id].add(tick, line, importance)


def seed_evidence(memories: Memories, evidence: dict[str, list[str]], tick: int) -> None:
    """Give each NPC its private starting memories. Very important (9), kind "evidence".

    Sorted by npc id so the order of memories is the same every run.
    """
    for npc_id in sorted(evidence):
        for line in evidence[npc_id]:
            memories[npc_id].add(tick, line, 9, "evidence")


REFLECTION_SCHEMA = {
    "type": "object",
    "properties": {"thoughts": {"type": "string", "maxLength": REFLECTION_MAX_CHARS}},
    "required": ["thoughts"],
}


def reflect(stream: MemoryStream, npc_name: str, client, tick: int) -> Memory | None:
    """Ask the model what this NPC now believes. None if the model fails."""
    # Evidence always goes in: it is what this NPC knows for certain.
    # (In the trial run Victor reflected without it and decided he was "framed".)
    evidence = [m for m in stream.memories if m.kind == "evidence"]
    recent = [m for m in stream.memories[-REFLECTION_INPUT:] if m.kind != "evidence"]
    lines = "\n".join(f"- {m.text}" for m in [*evidence, *recent])
    messages = [
        {
            "role": "system",
            # In character, first person. The trial run's replies began with
            # "The user is asking..." or a numbered plan, because nothing said who is thinking.
            "content": f"You are {npc_name}, a villager. Stay in character. "
            f"Your memories:\n{lines}",
        },
        {
            "role": "user",
            "content": "Think to yourself, in first person: in 1 to 3 short sentences, "
            "what do you now believe and suspect?",
        },
    ]
    try:
        thoughts = client.chat(messages, REFLECTION_SCHEMA)["thoughts"]
    except (LLMError, KeyError, TypeError):
        return None  # a missed reflection is fine: the next one will catch up
    # The server does not always enforce maxLength, so trim here and flatten newlines.
    thoughts = " ".join(str(thoughts).split())[:REFLECTION_MAX_CHARS]
    return stream.add(tick, thoughts, REFLECTION_IMPORTANCE, "reflection")
