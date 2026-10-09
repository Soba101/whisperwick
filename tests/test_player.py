"""Player actor tests: a normal NPC to the engine, never driven by code agents."""

from helpers import fresh_world, run_ticks

from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.llm_client import FakeClient
from whisperwick.llm_sim import run_llm
from whisperwick.memory import Memories
from whisperwick.player import PLAYER_ID
from whisperwick.stub_agent import intents_for_tick


def test_player_is_a_normal_npc_at_the_market():
    npc = fresh_world().npcs[PLAYER_ID]
    assert (npc.name, npc.location, npc.alive) == ("Wren", "loc_market", True)


def test_player_intents_are_accepted_and_rejected_like_npcs():
    w = fresh_world()
    assert w.act({"actor": PLAYER_ID, "action": "move", "target": "loc_inn"}).ok
    assert w.npcs[PLAYER_ID].location == "loc_inn"
    # No teleporting for the player either, and a rejection changes nothing.
    before = w.state_hash()
    bad = w.act({"actor": PLAYER_ID, "action": "move", "target": "loc_town_hall"})
    assert not bad.ok and bad.reason
    assert w.state_hash() == before


def test_npcs_witness_and_remember_player_actions():
    w, mem = fresh_world(), Memories()
    event = w.act(
        {"actor": PLAYER_ID, "action": "talk", "target": "npc_bob", "message": "Hello"}
    ).event
    # Bob is the target and Victor overhears: both are witnesses.
    assert {"npc_bob", "npc_victor"} <= set(event.witnesses)
    mem.observe(event, w)
    assert "Wren (player) said to you" in mem["npc_bob"].memories[0].text
    assert mem["npc_victor"].memories  # the overhearer remembers too
    # The player is a human: no memory stream is made for them.
    assert PLAYER_ID not in mem


def test_stub_agent_never_moves_the_player():
    w = fresh_world()
    run_ticks(w, 300)
    assert w.npcs[PLAYER_ID].location == "loc_market"
    assert all(e.actor != PLAYER_ID for e in w.log.all())
    assert all(i.actor != PLAYER_ID for i in intents_for_tick(w))


class RecordingClient(FakeClient):
    """Always looks; records who each model call is for (by the prompt's first line)."""

    def chat(self, messages, schema):
        if "thoughts" in schema["properties"]:
            self.calls.append(messages[0]["content"])
            return {"thoughts": "quiet"}
        self.calls.append(messages[0]["content"].splitlines()[0])
        return {"action": "look", "target": None, "item": None, "message": None}


def test_run_loop_never_asks_the_model_for_the_player():
    w, client = fresh_world(), RecordingClient([])
    memories, _ = run_llm(w, client, MINUTES_PER_DAY)
    assert client.calls
    assert not any("player" in str(c) and "Wren" in str(c).split("\n")[0] for c in client.calls)
    assert PLAYER_ID not in memories
