"""Rebuild saved turns through the normal loop, and stop on measurable drift."""

from dataclasses import dataclass, field

from whisperwick.agent_log import AgentLog
from whisperwick.belief_log import BeliefLog
from whisperwick.llm_sim import run_llm
from whisperwick.memory import Memories
from whisperwick.notebook import Notebooks
from whisperwick.repeat_guard import ActionHistory
from whisperwick.scenario import build_world, load_scenario
from whisperwick.screen_source import ReplayClient, Source
from whisperwick.world import World


@dataclass
class Context:
    """Keep replay state together so callbacks inspect the same turn context."""
    # The callback sees the live state before the saved reply is applied.
    world: World
    personalities: dict
    evidence: dict
    agent_memory: bool
    memories: Memories = field(default_factory=Memories)
    history: ActionHistory = field(default_factory=ActionHistory)
    belief_log: BeliefLog = field(default_factory=BeliefLog)
    notebooks: Notebooks = field(default_factory=Notebooks)
    agent_log: AgentLog = field(default_factory=AgentLog)


def replay(db, on_turn=None):
    """Return the source and rebuilt context. Callback signature: (context, npc, kind)."""
    source = Source(db)
    data = source.sidecar
    if data.get("group_turns", False):
        raise ValueError("Model screen replay requires group_turns off; this source has it on.")
    sc = load_scenario(data["scenario"])
    # Reuse the saved seed while keeping replay events out of the source database.
    world = build_world(sc, ":memory:", data.get("seed", sc.seed))
    c = Context(world, sc.personality, sc.evidence, data.get("agent_memory", False))
    client = ReplayClient(source, c, on_turn)
    try:
        # Serial thoughts keep callbacks in the same order as saved records.
        run_llm(world, client, data["minutes"], memories=c.memories, evidence=c.evidence,
                personalities=c.personalities, belief_log=c.belief_log, parallel=1,
                agent_memory=c.agent_memory, notebooks=c.notebooks, agent_log=c.agent_log,
                on_turn=client.turn, history=c.history)
    # A failed replay has no caller to close its temporary database.
    except BaseException:
        world.log.db.close()
        raise
    return source, c


def difference(source, c):
    """The first differing record, including the values needed to inspect it."""
    # Compare event facts without depending on database row ids.
    fields = ("type", "tick", "actor", "location", "data", "witnesses")
    expected = [{k: getattr(e, k) for k in fields} for e in source.events]
    actual = [{k: getattr(e, k) for k in fields} for e in c.world.log.all()]
    for label, saved, rebuilt in (
        ("events", expected, actual),
        ("beliefs", source.beliefs, c.belief_log.records),
    ):
        for i, (a, b) in enumerate(zip(saved, rebuilt, strict=False)):
            if a != b:
                return f"{label}[{i}]: saved={a!r}; replay={b!r}"
        # A matching prefix can still hide missing or extra records.
        if len(saved) != len(rebuilt):
            return f"{label} length: saved={len(saved)}; replay={len(rebuilt)}"
    # Final notes can drift even when events and beliefs match.
    saved = source.sidecar.get("notebooks", {})
    if saved != c.notebooks.to_dict():
        return f"notebooks: saved={saved!r}; replay={c.notebooks.to_dict()!r}"
    return None


def check(db):
    """A structured result lets both the CLI and callers refuse a drifting source."""
    source, c = replay(db)
    try:
        drift = difference(source, c)
        return {"ok": drift is None, "difference": drift,
                "unused_recalls": source.unused_recalls}
    finally:
        c.world.log.db.close()
