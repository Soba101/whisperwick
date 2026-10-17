"""Web play: the player queue, the state snapshot, the server and the page. No network."""

import http.client
import json
import re

import pytest
from helpers import SCENARIO, fresh_world
from web_helpers import Client, game_server, patch_model, shut

from whisperwick import web_guide, web_page, web_state
from whisperwick.actions import ActionResult, Intent
from whisperwick.player import PLAYER_ID
from whisperwick.player_web import WebPlayer, intent_from
from whisperwick.scenario import load_scenario

SC = load_scenario(SCENARIO)


def ask(player, world, kind, data=None):
    """Queue something for Wren, then run one turn(). Returns what turn() answered."""
    player.awaiting = True  # as if turn() were already waiting
    assert player.submit(kind, data)
    return player.turn(world)


# ---- the player queue ----

def test_act_wait_and_quit():
    w, p = fresh_world(), WebPlayer(SC)
    intent = Intent(actor=PLAYER_ID, action="look")
    assert ask(p, w, "act", intent) == [intent]
    p.auto_left = 0  # (the automatic wait after an action has its own tests)
    # A wait of 3 minutes: three quiet turns, and nobody is asked in between.
    assert ask(p, w, "wait", 3) == []
    assert p.turn(w) == [] and p.turn(w) == []
    assert p.wait_left == 0
    assert ask(p, w, "quit") is None and p.finished and p.outcome is not None


def test_submit_is_refused_when_it_is_not_wrens_turn():
    p = WebPlayer(SC)
    assert not p.submit("quit", None)  # nobody is waiting yet


def test_stop_ends_a_waiting_turn():
    w, p = fresh_world(), WebPlayer(SC)
    p.stop()
    assert p.turn(w) is None


def test_report_keeps_the_rejection_reason_until_the_next_action():
    p = WebPlayer(SC)
    intent = Intent(actor=PLAYER_ID, action="take", item="item_knife")
    p.report(intent, ActionResult(False, "not here"))
    assert p.snapshot()["rejection"] == "not here"
    p.report(intent, ActionResult(True))
    assert p.snapshot()["rejection"] is None


def test_intent_from_only_allows_wrens_actions():
    assert intent_from({"action": "talk", "target": "npc_bob", "message": "hi"}).message == "hi"
    assert intent_from({"action": "arrest", "target": "npc_bob"}) is None
    assert intent_from({"action": "talk", "target": ["x"]}) is None
    assert intent_from({"action": "look", "target": ""}).target is None


# ---- the snapshot ----

def test_snapshot_shows_only_what_wren_sees():
    w, p = fresh_world(), WebPlayer(SC)
    with p.cv:
        p._refresh(w)  # the first picture, as turn() takes it
    snap = p.snapshot()
    here = {x["id"] for x in snap["you"]["people"]}
    assert here == {"npc_bob", "npc_victor"}  # Alice, Sarah and Hal are elsewhere
    text = json.dumps(snap).lower()
    for hidden in ("npc_alice", "npc_sarah", "npc_hal", "npc_mayor", "belief", "murderer"):
        assert hidden not in text
    assert snap["outcome"] is None and snap["secret"] is None
    assert [e["id"] for e in snap["you"]["exits"]] == sorted(
        w.locations[w.npcs[PLAYER_ID].location].links)


def test_actions_offer_valid_choices_and_no_authority_actions():
    w = fresh_world()
    w.act(Intent(actor=PLAYER_ID, action="move", target="loc_town_hall"))
    acts = {a["action"]: a for a in web_state.actions_for(web_state.you_view(w))}
    assert "arrest" not in acts and "release" not in acts
    assert {t["id"] for t in acts["talk"]["targets"]} == {"npc_hal"}
    assert acts["talk"]["message"]
    assert acts["drop"]["reason"] == "you carry nothing"  # nothing carried
    assert [i["id"] for i in acts["take"]["items"]] == ["item_knife"]
    assert acts["move"]["targets"] and acts["look"]["targets"] is None


def test_finish_view_has_outcome_and_secret():
    text, secret = web_state.finish_view(fresh_world(), SC)
    assert text == "Nobody was arrested." and secret.startswith("murderer = ")


# ---- a real local server and a short game ----

@pytest.fixture
def game(monkeypatch, tmp_path):
    patch_model(monkeypatch)
    servers = []

    def start(minutes):
        server, manager = game_server(tmp_path, minutes)
        servers.append((server, manager))
        browser = Client(server.server_address[1])
        browser.request("/")  # opening the page starts this browser's game
        return browser

    yield start
    for server, manager in servers:
        shut(server, manager)


def test_full_loop_over_http(game):
    c = game(30)  # long enough for the automatic wait after an action
    s = c.until(lambda s: s["awaiting"])
    assert s["you"]["place"]["id"] == "loc_market"
    # Late or odd requests are refused, and not queued.
    assert c.request("/act", {"action": "arrest", "target": "npc_bob"})[0] == 400
    assert c.request("/wait", {"minutes": 7})[0] == 404
    code, _ = c.request("/act", {"action": "talk", "target": "npc_bob", "message": "hello"})
    assert code == 200
    # The engine judges the next one: the knife is not at the Market.
    c.until(lambda s: s["awaiting"] and any("hello" in x for x in s["feed"]))
    c.request("/act", {"action": "take", "item": "item_knife"})
    s = c.until(lambda s: s["awaiting"] and s["rejection"])
    assert s["rejection"]  # the engine's own reason, shown as given
    # Only new lines come back when `since` is given.
    assert c.state(since=s["feed_total"])["feed"] == []
    assert c.request("/wait", {"minutes": 60})[0] == 200
    s = c.until(lambda s: s["finished"])
    assert s["outcome"] and s["secret"].startswith("murderer = ")
    assert not s["awaiting"]


def test_quit_over_http(game):
    c = game(100)
    c.until(lambda s: s["awaiting"])
    assert c.state()["outcome"] is None and c.state()["secret"] is None
    assert c.request("/quit", {})[0] == 200
    assert c.until(lambda s: s["finished"])["outcome"]


def test_server_refuses_foreign_hosts_and_form_posts(game):
    c = game(5)
    c.until(lambda s: s["awaiting"])
    assert c.request("/state", headers={"Host": "evil.test"})[0] == 403
    # A POST without the JSON content type (like a plain cross-site form) is refused.
    conn = http.client.HTTPConnection("127.0.0.1", c.port, timeout=5)
    conn.request("POST", "/quit", "{}", {"Cookie": f"ww_game={c.cookies['ww_game']}"})
    assert conn.getresponse().status == 400


# ---- the page ----

def test_page_is_offline_and_has_no_plot_words():
    html = web_page.render_page()
    assert not re.search(r"https?://|src=|href=|@import", html)
    assert html.count(web_guide.HOOK) == 2
    text = html.replace(web_guide.HOOK, "").lower()
    for word in ("murder", "mayor", "killer"):
        assert word not in text
    assert "You are Wren, a newcomer" in html
    assert html.count("innerHTML +=") == 1 and "innerHTML =" not in html  # svg lines only


BANNED = ("murder", "mayor", "killer", "body", "crime", "mystery", "clue", "suspect", "detective")


def test_guide_sections_and_button():
    html = web_page.render_page()
    for heading in ("How to play", "Who you are", "What this is", "The screen",
                    "Taking a turn", "Time", "The end", "Try first"):
        assert f">{heading}</h" in html
    assert ">Start playing</button>" in html
    assert 'aria-label="How to play">How to play</button>' in html


def test_hint_lines_are_in_the_page():
    html = web_page.render_page()
    assert 'id="hint"' in html
    for text in ("Your turn: choose what Wren does, then press Send.",
                 "The villagers are acting. Wait a moment...",
                 "Type what you want to say."):
        assert text in html


def test_action_labels_are_friendly():
    labels = [a["label"] for a in web_state.actions_for(
        {"people": [{"id": "p"}], "ground": [{"id": "g"}], "carried": [{"id": "c"}],
         "exits": [{"id": "e"}]})]
    assert labels == ["Go to", "Look around", "Talk to", "Take", "Drop", "Give", "Show"]


def test_guide_has_no_plot_words():
    # Checked on the guide text only: the page script and CSS legitimately say "body".
    text = (web_guide.GUIDE + " ".join(web_guide.HINTS.values()))
    text = text.replace(web_guide.HOOK, "").lower()
    for word in BANNED:
        assert not re.search(rf"\b{word}", text), word


def test_hook_names_no_villager_or_clue():
    for word in ("Alice", "Bob", "Hal", "Sarah", "Victor", "murderer", "killer",
                 "knife", "boots", "clue", "suspect"):
        assert not re.search(rf"\b{word}\b", web_guide.HOOK, re.IGNORECASE)


def test_empty_choices_keep_all_actions_with_reasons():
    acts = {a["action"]: a for a in web_state.actions_for(
        {"people": [], "ground": [], "carried": [], "exits": [{"id": "loc_inn"}]})}
    assert len(acts) == 7
    assert {a for a, row in acts.items() if row["reason"] is None} == {"move", "look"}
    assert acts["take"]["reason"] == "nothing to take here"
    assert acts["drop"]["reason"] == "you carry nothing"
    assert acts["give"]["reason"] == acts["show"]["reason"] == "you carry nothing"
    assert acts["talk"]["reason"] == "nobody here to talk to"


def test_every_action_and_scenario_place_has_an_icon():
    from whisperwick.web_icons import ACTION_ICONS, PLACE_ICONS

    acts = web_state.actions_for(web_state.you_view(fresh_world()))
    assert len(acts) == 7 and all(a["icon"] == ACTION_ICONS[a["action"]] for a in acts)
    places = web_state.map_data(SC)
    assert {p["id"] for p in places} == {p.id for p in SC.locations}
    assert all(p["icon"] == PLACE_ICONS[p["id"]] for p in places)
