"""Quiet replies come from completed turns, without changing the event log."""

import pytest
from helpers import fresh_world
from web_helpers import SC

from whisperwick import story
from whisperwick.actions import Intent
from whisperwick.player import PLAYER_ID
from whisperwick.player_web import WebPlayer


def talk_to(player, world, npc_id="npc_bob"):
    """Hand Wren's talk to the loop just as the page does."""
    intent = Intent(actor=PLAYER_ID, action="talk", target=npc_id, message="hello")
    player.awaiting = True
    assert player.submit("act", intent)
    assert player.turn(world) == [intent]
    world.act(intent)
    player.on_turn(world, npc_id)


@pytest.mark.parametrize("errored", [False, True])
def test_quiet_turn_is_shown_once_and_ends_auto_wait(errored):
    w, p = fresh_world(), WebPlayer(SC)
    p.stats = {"errors": 2}
    talk_to(p, w)
    tick = w.clock.tick  # Bob's turn starts now
    before = list(w.log.all())
    w.clock.advance()  # closed a minute later: the line still shows Bob's own minute
    if errored:
        p.stats["errors"] += 1
    p.on_turn(w, "npc_victor")
    words = "(Bob did not answer)" if errored else "Bob looks around"
    place = w.locations[w.npcs[PLAYER_ID].location].name
    assert p.feed[-1] == f"{story.hhmm(tick)}  {place.ljust(story.PLACE_WIDTH)} {words}"
    assert w.log.all() == before
    assert p.others == p.others_at_act + 1 and p.lines_by["npc_bob"] == 1
    assert p.waiting_on is None and p.turn_of is None
    p.on_turn(w, None)
    assert sum(words in line for line in p.feed) == 1
    p.awaiting = True
    assert p.submit("wait", 1)
    assert p.turn(w) == [] and p.auto_left == 0


def test_real_talk_gets_no_extra_line():
    w, p = fresh_world(), WebPlayer(SC)
    talk_to(p, w)
    w.act(Intent(actor="npc_bob", action="talk", target="npc_victor", message="Good day"))
    p.on_event(w, w.log.all()[-1])
    p.on_turn(w, "npc_victor")
    assert p.feed[-1].endswith('Bob -> Victor: "Good day"')
    assert p.lines_by["npc_bob"] == 1 and p.others == 1


def test_unaddressed_villager_adds_nothing():
    w, p = fresh_world(), WebPlayer(SC)
    talk_to(p, w)
    p.on_turn(w, "npc_victor")  # This closes Bob's turn.
    before = list(p.feed)
    p.on_turn(w, None)
    assert p.feed == before


def test_villager_elsewhere_adds_nothing():
    w, p = fresh_world(), WebPlayer(SC)
    talk_to(p, w, "npc_alice")
    before = list(p.feed)
    p.on_turn(w, None)
    assert p.feed == before and p.others == 0


@pytest.mark.parametrize("close", ["refresh", "finish"])
def test_last_quiet_turn_closes_without_another_villager(close):
    w, p = fresh_world(), WebPlayer(SC)
    talk_to(p, w)
    if close == "finish":
        p.finish()
    else:
        with p.cv:
            p._refresh(w)
    assert p.feed[-1].endswith("Bob looks around")
