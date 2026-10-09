"""Beliefs: each rule, the three-hop chain, replay, saving, and the scenario."""

import json

import pytest
from helpers import SCENARIO, fresh_world

from whisperwick.beliefs import BeliefState, replay
from whisperwick.events import Event
from whisperwick.scenario import check_references, load_scenario

SC = load_scenario(SCENARIO)


def say(w, actor, to, kind, subject):
    r = w.act({"actor": actor, "action": "talk", "target": to, "message": "psst",
               "claim": {"kind": kind, "subject": subject}})  # fmt: skip
    assert r.ok, r.reason
    return r.event


def test_starting_beliefs_are_saw_sources_with_no_event():
    s = BeliefState.from_scenario(SC)
    assert s.confidence("npc_bob", "npc_victor") == 0.5
    assert s.confidence("npc_victor", "npc_victor") == 1.0
    assert s.top("npc_hal") is None
    src = s.sources_before("npc_bob", "npc_victor", 1)[0]  # starting sources always count
    assert (src.type, src.event_id, src.tick) == ("saw", None, 480)
    assert s.top("npc_victor", exclude=("npc_victor",)) is None


def test_top_breaks_ties_by_id():
    s = BeliefState.from_scenario(SC)
    s._set("npc_hal", "npc_zed", 0.3)
    s._set("npc_hal", "npc_abe", 0.3)
    assert s.top("npc_hal") == ("npc_abe", 0.3)


def test_killer_claim_raises_and_innocent_lowers():
    w = fresh_world()
    s = BeliefState.from_scenario(SC)
    s.apply(say(w, "npc_victor", "npc_bob", "killer", "npc_hal"))
    assert s.confidence("npc_bob", "npc_hal") == pytest.approx(0.25)  # 0.5 * 0.5
    s.apply(say(w, "npc_victor", "npc_bob", "innocent", "npc_hal"))
    # Bob firmly saw Victor, so the first claim cost Victor's trust (0.5 -> 0.35).
    # Then: 0.25 - 0.25 * 0.35 * 0.5
    assert s.confidence("npc_bob", "npc_hal") == pytest.approx(
        0.2062
    )  # stored rounded to 4 decimals
    notes = [x.note for x in s.sources["npc_bob"]["npc_hal"]]
    assert notes == ["said killer", "said innocent"]


def test_overhearers_believe_too_but_the_player_never_does():
    w = fresh_world()
    s = BeliefState.from_scenario(SC)
    s.apply(say(w, "npc_bob", "npc_victor", "killer", "npc_hal"))
    # Bob talks at the market: Victor hears it, the player overhears, and neither is Bob.
    assert s.confidence("npc_victor", "npc_hal") > 0
    assert "player" not in s.conf


def test_shown_clue_points_witnesses_at_the_owner():
    w = fresh_world()
    s = BeliefState.from_scenario(SC)
    w.items["item_boots"].holder = "npc_bob"  # Bob holds Victor's boots
    w.npcs["npc_alice"].location = "loc_market"  # Alice walks in and sees them
    ev = w.act({"actor": "npc_bob", "action": "show", "item": "item_boots"}).event
    s.apply(ev)
    assert s.confidence("npc_alice", "npc_victor") == pytest.approx(0.5 + 0.3 * 0.5)
    assert s.sources["npc_alice"]["npc_victor"][-1].event_id == ev.id
    # Sarah is in the temple, so she saw nothing. The owner and the player gain nothing.
    assert s.confidence("npc_sarah", "npc_victor") == 0.2
    assert s.confidence("npc_victor", "npc_victor") == 1.0
    assert "player" not in s.conf


def test_given_clue_counts_the_recipient():
    w = fresh_world()
    s = BeliefState.from_scenario(SC)
    w.items["item_boots"].holder = "npc_bob"
    w.npcs["npc_sarah"].location = "loc_market"
    ev = w.act({"actor": "npc_bob", "action": "give", "item": "item_boots",
                "target": "npc_sarah"}).event  # fmt: skip
    s.apply(ev)
    assert s.confidence("npc_sarah", "npc_victor") == pytest.approx(0.2 + 0.3 * 0.8)
    assert s.sources["npc_sarah"]["npc_victor"][-1].note == "saw the muddy boots given"


def test_non_clue_item_and_plain_events_change_nothing():
    w = fresh_world()
    s = BeliefState.from_scenario(SC)
    before = json.dumps([s.conf, s.trust.to_dict()], default=vars, sort_keys=True)
    w.items["item_boots"].holder = "npc_bob"
    s.clues.pop("item_boots")  # now the boots are just an item
    s.apply(w.act({"actor": "npc_bob", "action": "show", "item": "item_boots"}).event)
    s.apply(w.act({"actor": "npc_bob", "action": "talk", "target": "npc_victor",
                   "message": "hello"}).event)  # fmt: skip
    s.apply(w.act({"actor": "npc_bob", "action": "move", "target": "loc_inn"}).event)
    assert json.dumps([s.conf, s.trust.to_dict()], default=vars, sort_keys=True) == before
    assert len(s.sources) == 4  # only the starting sources exist


def test_three_hop_chain_is_traceable():
    w = fresh_world()
    # Put the whole chain in one room so every talk is legal.
    # The clock never advances here: all three talks share one tick, and event ids
    # alone keep the order (an NPC can relay a rumour the minute it hears it).
    for n in ("npc_bob", "npc_alice", "npc_hal"):
        w.npcs[n].location = "loc_market"
    s = BeliefState.from_scenario(SC)
    e1 = say(w, "player", "npc_bob", "killer", "npc_hal")  # the lie
    s.apply(e1)
    e2 = say(w, "npc_bob", "npc_alice", "killer", "npc_hal")
    s.apply(e2)
    e3 = say(w, "npc_alice", "npc_hal", "killer", "npc_hal")
    s.apply(e3)
    # Hal heard a rumour about himself: no belief, but the others hold it.
    assert s.confidence("npc_hal", "npc_hal") == 0.0
    # Walk back from Alice: told by Bob in e2; Bob had a source before e2 (told by player in e1).
    told = s.sources_before("npc_alice", "npc_hal", e3.id)
    assert [(x.by, x.event_id) for x in told if x.event_id == e2.id] == [("npc_bob", e2.id)]
    bob_before = s.sources_before("npc_bob", "npc_hal", e2.id)
    assert [(x.type, x.by, x.event_id) for x in bob_before] == [("told", "player", e1.id)]
    # And the player had nothing: that claim was their own lie.
    assert s.sources_before("player", "npc_hal", e1.id) == []
    assert e1.tick == e2.tick == e3.tick


def test_same_tick_relay_still_shows_bobs_source_before_his_relay():
    w = fresh_world()
    w.npcs["npc_alice"].location = "loc_market"
    s = BeliefState.from_scenario(SC)
    e1 = say(w, "player", "npc_bob", "killer", "npc_hal")
    e2 = say(w, "npc_bob", "npc_alice", "killer", "npc_hal")
    s.apply(e1)
    s.apply(e2)
    assert e1.tick == e2.tick
    assert [x.event_id for x in s.sources_before("npc_bob", "npc_hal", e2.id)] == [e1.id]
    # Before the lie itself, Bob knew nothing about Hal.
    assert s.sources_before("npc_bob", "npc_hal", e1.id) == []


def tell(teller, hearer, kind, subject, eid):
    """A talk event built by hand, so the speakers need not be in the same place."""
    return Event(
        id=eid, tick=500, type="talk", actor=teller, location="loc_market",
        data={"to": hearer, "message": "x", "claim": {"kind": kind, "subject": subject}},
        witnesses=[hearer],
    )  # fmt: skip


def test_same_claim_from_same_teller_is_ignored_after_the_first_time():
    s = BeliefState.from_scenario(SC)
    s.apply(tell("npc_victor", "npc_bob", "killer", "npc_hal", 1))
    snap = json.dumps(s.to_dict(), sort_keys=True)
    for eid in range(2, 7):
        s.apply(tell("npc_victor", "npc_bob", "killer", "npc_hal", eid))
    # Nothing changed: not confidence, sources or trust (the saved state is identical).
    assert json.dumps(s.to_dict(), sort_keys=True) == snap
    assert len(s.sources["npc_bob"]["npc_hal"]) == 1
    # A different teller, or the opposite claim, still counts.
    s.apply(tell("npc_alice", "npc_bob", "killer", "npc_hal", 7))
    s.apply(tell("npc_victor", "npc_bob", "innocent", "npc_hal", 8))
    assert len(s.sources["npc_bob"]["npc_hal"]) == 3


def test_repeat_is_tracked_per_hearer():
    s = BeliefState.from_scenario(SC)
    s.apply(tell("npc_victor", "npc_bob", "killer", "npc_hal", 1))
    # Alice did not hear it the first time, so for her it is new.
    s.apply(tell("npc_victor", "npc_alice", "killer", "npc_hal", 2))
    assert s.confidence("npc_alice", "npc_hal") > 0


def test_heard_is_saved_sorted_and_old_dicts_still_load():
    s = BeliefState.from_scenario(SC)
    s.apply(tell("npc_victor", "npc_bob", "killer", "npc_hal", 1))
    s.apply(tell("npc_alice", "npc_bob", "innocent", "npc_hal", 2))
    d = json.loads(json.dumps(s.to_dict()))
    assert d["heard"] == sorted(d["heard"]) and len(d["heard"]) == 2
    assert BeliefState.from_dict(d).heard == s.heard
    del d["heard"]  # a file saved before this key existed
    assert BeliefState.from_dict(d).heard == set()


def test_replay_equals_live_and_round_trips():
    w = fresh_world()
    s = BeliefState.from_scenario(SC)
    w.items["item_boots"].holder = "npc_bob"
    for ev in (
        say(w, "player", "npc_bob", "killer", "npc_hal"),
        say(w, "npc_victor", "npc_bob", "innocent", "npc_victor"),
        w.act({"actor": "npc_bob", "action": "show", "item": "item_boots"}).event,
    ):
        s.apply(ev)
    again = replay(w.log.all()[::-1], SC)  # shuffled input: replay sorts by id
    assert again.to_dict() == s.to_dict()
    saved = json.loads(json.dumps(s.to_dict()))
    assert BeliefState.from_dict(saved).to_dict() == s.to_dict()


def test_scenario_sections_load():
    assert SC.trust == {"default": 0.5, "player": 0.3}
    assert SC.clues == {"item_knife": "npc_victor", "item_boots": "npc_victor"}
    assert "npc_hal" not in SC.beliefs and "npc_hal" in SC.goals
    check_references(SC)


@pytest.mark.parametrize(
    "field,value",
    [
        ("clues", {"item_nope": "npc_victor"}),
        ("clues", {"item_knife": "npc_nobody"}),
        ("beliefs", {"npc_nobody": []}),
        ("goals", {"npc_nobody": "x"}),
        ("trust", {"default": 1.5}),
        ("trust", {"bob": 0.5}),
        ("beliefs", {"npc_bob": [{"subject": "npc_nobody", "confidence": 0.5, "note": "x"}]}),
    ],
)
def test_bad_references_fail(field, value):
    # Rebuild through validation so nested dicts become real models.
    raw = load_scenario(SCENARIO).model_dump()
    bad = type(SC).model_validate({**raw, field: value})
    with pytest.raises(ValueError):
        check_references(bad)
