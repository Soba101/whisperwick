"""After Wren acts, the web player waits for a reply on its own. No network."""

from helpers import fresh_world
from web_helpers import SC

from whisperwick import web_guide, web_page
from whisperwick.actions import ActionResult, Intent
from whisperwick.clock import Clock
from whisperwick.player import PLAYER_ID
from whisperwick.player_web import AUTO_WAIT_MAX, WebPlayer

TALK = Intent(actor=PLAYER_ID, action="talk", target="npc_bob", message="hello")


def act(player, world):
    """Queue one action, as the page would, and run one turn()."""
    player.awaiting = True
    assert player.submit("act", TALK)
    return player.turn(world)


def bob_speaks(world, player):
    """Bob (same place as Wren) talks to her: a line she can see, not caused by her."""
    world.act(Intent(actor="npc_bob", action="talk", target=PLAYER_ID, message="hi"))
    player.on_event(world, world.log.all()[-1])


def test_quiet_until_someone_answers_then_the_page_is_asked():
    w, p = fresh_world(), WebPlayer(SC)
    assert act(p, w) == [TALK]
    w.act(TALK)
    p.on_event(w, w.log.all()[-1])  # her own line does not end the wait
    assert p.turn(w) == [] and p.snapshot()["auto_wait"]
    assert p.turn(w) == []
    bob_speaks(w, p)
    p.awaiting = True
    p.submit("quit", None)  # the page is asked now: this quit is what it answers
    assert p.turn(w) is None and not p.snapshot()["auto_wait"]


def test_auto_wait_stops_after_the_cap():
    w, p = fresh_world(), WebPlayer(SC)
    act(p, w)
    assert [p.turn(w) for _ in range(AUTO_WAIT_MAX)] == [[]] * AUTO_WAIT_MAX
    assert p.auto_left == 0
    p.awaiting = True
    p.submit("wait", 1)  # an eleventh turn asks the page, which answers a wait
    assert p.turn(w) == []


def test_rejected_action_does_not_wait():
    w, p = fresh_world(), WebPlayer(SC)
    act(p, w)
    p.report(TALK, ActionResult(False, "not here"))
    assert p.auto_left == 0 and not p.snapshot()["auto_wait"]
    p.stop()
    assert p.turn(w) is None  # it came back to the page (stopped while asking)


def test_quit_during_auto_wait_ends_the_game():
    w, p = fresh_world(), WebPlayer(SC)
    act(p, w)
    assert p.turn(w) == []
    assert p.submit("quit", None)  # accepted although Wren is not being asked
    assert p.turn(w) is None and p.finished


def test_stop_during_auto_wait_ends_the_game():
    w, p = fresh_world(), WebPlayer(SC)
    act(p, w)
    p.stop()
    assert p.turn(w) is None and p.finished


def test_night_gives_the_turn_back():
    w, p = fresh_world(), WebPlayer(SC)
    w.clock = Clock.at(1, 22, 0)
    act(p, w)
    p.stop()  # the turn came back to the page, which sees the stop
    assert p.turn(w) is None


def test_hint_text_is_in_the_page():
    assert web_guide.HINTS["auto"] == "Waiting for a reply..."
    assert "Waiting for a reply..." in web_page.render_page()
