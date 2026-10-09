"""A small rumour for the trace and belief-report tests: real talks, hand-written beliefs.

The world and events are real (World.act, Memories.observe). Only the beliefs are written
by hand, because they are model output. No model is called.
"""

from helpers import SCENARIO

from whisperwick.belief_log import BeliefLog
from whisperwick.memory import Memories, memory_id
from whisperwick.scenario import build_world, load_scenario

HAL = {"kind": "killer", "subject": "npc_hal"}


def new_world(db=":memory:"):
    """Alice, Bob, Victor, Sarah and the player all stand in the market, so all can talk."""
    world = build_world(load_scenario(SCENARIO), str(db))
    for who in ("npc_alice", "npc_sarah", "npc_hal"):
        world.npcs[who].location = "loc_market"
    return world, Memories(), BeliefLog()


def talk(world, memories, actor, to, message, claim=None):
    """A real talk through the engine, then everyone who saw it remembers it. Returns the event."""
    intent = {"actor": actor, "action": "talk", "target": to, "message": message}
    if claim:
        intent["claim"] = claim
    result = world.act(intent)
    assert result.ok, result.reason
    memories.observe(result.event, world)
    return result.event


def cite(memories, npc, event):
    """The citation a villager would give for its memory of this event."""
    for i, m in enumerate(memories[npc].memories):
        if m.event_id == event.id:
            return {"memory_id": memory_id(i), "event_id": event.id, "text": m.text}
    raise AssertionError(f"{npc} has no memory of event {event.id}")


def belief(npc, after_event, suspect="npc_hal", sureness="fairly sure", because=(), **kw):
    """A belief record, shaped like thinking.py makes them."""
    record = {
        "tick": after_event, "npc": npc, "suspect": suspect, "of_what": "killing the mayor",
        "sureness": sureness, "thoughts": f"{npc} thinks.", "because": list(because),
        "trust": [], "hunch": suspect is not None and not because, "after_event": after_event,
    }  # fmt: skip
    return {**record, **kw}


def rumour():
    """Wren (the player) tells Bob 'Hal did it'; Bob tells Alice. Returns everything built."""
    world, memories, log = new_world()
    e1 = talk(world, memories, "player", "npc_bob", "Hal did it", HAL)
    log.add(belief("npc_bob", e1.id, because=[cite(memories, "npc_bob", e1)]))
    e2 = talk(world, memories, "npc_bob", "npc_alice", "Hal did it", HAL)
    log.add(belief("npc_alice", e2.id, because=[cite(memories, "npc_alice", e2)]))
    return world, memories, log, e1, e2
