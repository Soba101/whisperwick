"""Talk saves turns without changing who hears it. All model replies are fakes."""

import pytest
from helpers import fresh_world
from test_play import LookClient

from whisperwick.events import Event
from whisperwick.llm_sim import run_llm
from whisperwick.player_script import ScriptedPlayer
from whisperwick.scheduler import COOLDOWN, Scheduler


@pytest.mark.parametrize("message, named", [
    ("Ask ALICE, and Hal too.", True),
    ("Ask npc_alice, and Hal too.", True),
    ("Ask Rose, and Hal too.", True),
    ("Ask Malice, and Hal too.", False),
    ("Ask Al, and Hal too.", False),
])
@pytest.mark.parametrize("actor", ["player", "npc_victor"])
def test_callers_wake_only_listener_and_named_bystander(actor, message, named):
    world = fresh_world()
    for npc in ("player", "npc_alice", "npc_bob", "npc_sarah", "npc_victor"):
        world.npcs[npc].location = "loc_market"
    # A named villager elsewhere must not wake just because their name was said.
    world.npcs["npc_hal"].location = "loc_inn"
    world.npcs["npc_alice"].name = "Alice Rose"
    start, turns = world.clock.tick, []
    intent = {"actor": actor, "action": "talk", "target": "npc_bob", "message": message}

    class SpeakOnce(LookClient):
        def chat(self, messages, schema):
            if (actor == "npc_victor" and world.clock.tick == start
                    and "(npc_victor)" in messages[0]["content"]):
                return {k: v for k, v in intent.items() if k != "actor"}
            return super().chat(messages, schema)

    # Player and NPC talks happen after Alice's first turn, so a wake is observable.
    player = ScriptedPlayer({start + 1: [intent]}) if actor == "player" else None
    memories, _ = run_llm(
        world, SpeakOnce(), COOLDOWN + 2, player=player,
        on_turn=lambda w, npc: turns.append((w.clock.tick - start, npc)),
    )
    assert ((COOLDOWN, "npc_alice") in turns) == named
    assert [tick for tick, npc in turns if npc == "npc_bob"] == [
        0, 2 if actor == "player" else 1,
    ]
    for npc in ("npc_sarah", "npc_hal"):
        assert [tick for tick, who in turns if who == npc] == [0]
    # Unnamed witnesses still remember the exact same talk.
    for npc in ("npc_alice", "npc_sarah", "npc_bob"):
        assert any(message in m.text for m in memories[npc].memories)


@pytest.mark.parametrize("verb", [
    "move", "take", "show", "give", "drop", "arrest", "release", "look",
])
def test_non_talk_wakes_all_witnesses(verb):
    scheduler = Scheduler(["npc_alice", "npc_bob", "npc_carol"])
    for npc in scheduler.last:
        scheduler.acted(npc, 720)
    scheduler.notice(Event(
        tick=721, type=verb, actor="npc_alice", location="loc_inn",
        witnesses=["npc_carol", "npc_alice", "npc_bob"],
    ))
    assert scheduler.due(720 + COOLDOWN) == ["npc_bob", "npc_carol"]


def test_talk_named_set_cannot_wake_non_witnesses():
    scheduler = Scheduler(["npc_alice", "npc_bob", "npc_carol", "npc_dan"])
    for npc in scheduler.last:
        scheduler.acted(npc, 720)
    scheduler.notice(Event(
        tick=721, type="talk", actor="npc_alice", location="loc_inn",
        data={"to": "npc_bob"}, witnesses=["npc_alice", "npc_carol"],
    ), named=frozenset({"npc_alice", "npc_dan"}))
    assert scheduler.woken == {"npc_bob"}
    assert scheduler.due(722) == ["npc_bob"]
