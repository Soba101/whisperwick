"""Trust: defaults, the player's lower trust, and how claims move it."""

import pytest
from helpers import SCENARIO

from whisperwick.beliefs import BeliefState
from whisperwick.events import Event
from whisperwick.scenario import load_scenario
from whisperwick.trust import Trust

SC = load_scenario(SCENARIO)


def talk(actor, kind, subject, witnesses, eid=1):
    return Event(
        id=eid, tick=500, type="talk", actor=actor, location="loc_market",
        data={"to": witnesses[0], "message": "x", "claim": {"kind": kind, "subject": subject}},
        witnesses=witnesses,
    )  # fmt: skip


def test_defaults_and_unknown_pairs():
    t = BeliefState.from_scenario(SC).trust
    assert t.get("npc_bob", "npc_alice") == 0.5
    assert t.get("npc_bob", "player") == 0.3
    assert Trust().get("a", "b") == 0.5  # no scenario: built-in defaults


def test_player_claim_moves_belief_less():
    # Same claim, same hearer: the player is trusted less than a villager.
    from_player, from_alice = BeliefState.from_scenario(SC), BeliefState.from_scenario(SC)
    from_player.apply(talk("player", "killer", "npc_hal", ["npc_bob"], 2))
    from_alice.apply(talk("npc_alice", "killer", "npc_hal", ["npc_bob"], 2))
    assert from_player.confidence("npc_bob", "npc_hal") == pytest.approx(0.15)  # 0.3 * 0.5
    assert from_alice.confidence("npc_bob", "npc_hal") == pytest.approx(0.25)  # 0.5 * 0.5


def test_contradiction_drops_trust_agreement_raises_it():
    s = BeliefState.from_scenario(SC)
    # Bob starts firm about Victor (0.5 is at FIRM), so he can judge claims.
    assert s.trust.get("npc_bob", "npc_alice") == 0.5
    s.apply(talk("npc_alice", "killer", "npc_victor", ["npc_bob"]))  # agrees
    assert s.trust.get("npc_bob", "npc_alice") == pytest.approx(0.55)
    s.apply(talk("npc_alice", "killer", "npc_hal", ["npc_bob"], 2))  # clashes
    assert s.trust.get("npc_bob", "npc_alice") == pytest.approx(0.4)
    s.apply(talk("npc_alice", "innocent", "npc_victor", ["npc_bob"], 3))  # clashes
    assert s.trust.get("npc_bob", "npc_alice") == pytest.approx(0.25)


def test_weak_first_hand_belief_judges_nobody():
    # Sarah's 0.2 is under FIRM, so a contradicting claim leaves her trust alone.
    s = BeliefState.from_scenario(SC)
    s.apply(talk("npc_alice", "killer", "npc_hal", ["npc_sarah"]))
    assert s.trust.get("npc_sarah", "npc_alice") == 0.5


def test_players_lie_costs_the_player_trust():
    # Bob is firm on Victor, so "Hal is the killer" from the player clashes: 0.3 - 0.15.
    s = BeliefState.from_scenario(SC)
    s.apply(talk("player", "killer", "npc_hal", ["npc_bob"]))
    assert s.trust.get("npc_bob", "player") == pytest.approx(0.15)


def test_rumour_about_yourself_changes_trust_not_belief():
    s = BeliefState.from_scenario(SC)
    # Victor knows he did it (1.0, saw). Told "Victor is innocent" he is not swayed...
    s.apply(talk("npc_alice", "innocent", "npc_victor", ["npc_victor"]))
    assert s.confidence("npc_victor", "npc_victor") == 1.0
    # ...and a rumour that clashes with his own knowledge still costs trust.
    assert s.trust.get("npc_victor", "npc_alice") == pytest.approx(0.35)


def test_trust_is_clamped_and_round_trips():
    t = Trust()
    for _ in range(20):
        t.change("a", "b", -0.15)
    assert t.get("a", "b") == 0.0
    t.change("a", "c", 0.123456)
    assert Trust.from_dict(t.to_dict()).to_dict() == t.to_dict()
