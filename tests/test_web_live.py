"""Live feed hooks and the busy label. A fake model, no network."""

from helpers import fresh_world
from test_play import LookClient
from web_helpers import SC

from whisperwick.actions import Intent
from whisperwick.llm_sim import run_llm
from whisperwick.player import PLAYER_ID
from whisperwick.player_web import WebPlayer


class BobTalks(LookClient):
    """Bob talks to Victor (they share the market), so there are real events."""

    def chat(self, messages, schema):
        if "(npc_bob)" in messages[0]["content"] and "thoughts" not in schema["properties"]:
            return {"action": "talk", "target": "npc_victor", "message": "Good day"}
        return super().chat(messages, schema)


def test_hooks_fire_and_change_nothing():
    plain, hooked = fresh_world(), fresh_world()
    events, turns = [], []
    run_llm(plain, BobTalks(), 300)
    run_llm(
        hooked, BobTalks(), 300,
        on_event=lambda w, e: events.append(e.id),
        on_turn=lambda w, n: turns.append(n),
    )  # fmt: skip
    assert events and None in turns and any(t for t in turns)  # None = the thinking phase
    # The same events and the same state, with or without hooks.
    assert [e.model_dump() for e in plain.log.all()] == [e.model_dump() for e in hooked.log.all()]
    assert plain.state_hash() == hooked.state_hash()
    # Every hooked event is a real one from the log.
    assert set(events) <= {e.id for e in hooked.log.all()}


def test_events_reach_the_feed_before_the_next_turn():
    world, player = fresh_world(), WebPlayer(SC)
    world.act(Intent(actor="npc_bob", action="talk", target=PLAYER_ID, message="psst"))
    player.on_event(world, world.log.all()[-1])  # a line for Wren, shown at once
    assert any("psst" in line for line in player.feed)
    player.on_event(world, world.log.all()[-1])  # asking again adds nothing twice
    assert sum("psst" in line for line in player.feed) == 1


def test_busy_label_never_names_someone_outside_wrens_view():
    world, player = fresh_world(), WebPlayer(SC)
    here = world.npcs[PLAYER_ID].location
    near = next(n for n in world.npcs if n != PLAYER_ID and world.npcs[n].location == here)
    far = next(n for n in world.npcs if n != PLAYER_ID and world.npcs[n].location != here)
    player.on_turn(world, near)
    assert player.snapshot()["busy"] == f"{world.npcs[near].name} is thinking..."
    player.on_turn(world, far)
    label = player.snapshot()["busy"]
    assert label == "Someone elsewhere is acting..." and world.npcs[far].name not in label
    player.on_turn(world, None)
    assert "thinking about the day" in player.snapshot()["busy"]
    player.awaiting = True  # on Wren's turn there is nothing to wait for
    assert player.snapshot()["busy"] == ""
