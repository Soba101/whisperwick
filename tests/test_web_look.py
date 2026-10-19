"""Wren's own look shows up in her feed. A look is not a logged event."""

from helpers import SCENARIO, fresh_world

from whisperwick.actions import Intent, do_look
from whisperwick.player import PLAYER_ID
from whisperwick.player_web import WebPlayer
from whisperwick.scenario import load_scenario

SC = load_scenario(SCENARIO)


def test_look_adds_one_feed_line_with_what_wren_sees():
    w, p = fresh_world(), WebPlayer(SC)
    p.world = w  # as after a refresh
    look = Intent(actor=PLAYER_ID, action="look")
    p.report(look, do_look(w, look))
    assert len(p.feed) == 1
    line = p.feed[0]
    here = w.locations[w.npcs[PLAYER_ID].location].name
    assert f"{here}: You look around." in line
    # Only what the look itself returned: people here, ground items, exits.
    for n in w.npcs_at(w.npcs[PLAYER_ID].location):
        if n != PLAYER_ID:
            assert w.npcs[n].name in line
    assert "Exits:" in line


def test_a_refused_action_adds_no_feed_line():
    w, p = fresh_world(), WebPlayer(SC)
    p.world = w
    move = Intent(actor=PLAYER_ID, action="move", target="loc_nowhere")
    from whisperwick.actions import ActionResult
    p.report(move, ActionResult(False, reason="not reachable"))
    assert p.feed == [] and p.rejection == "not reachable"
