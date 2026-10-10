"""Custody: arrest and release are world facts, strict, logged, and never change state on reject.

Start: Hal (the only authority) is in the Town Hall with the dead mayor.
Victor and Bob are at the market with the player.
"""

import json

import pytest
from helpers import fresh_world

from whisperwick import belief_text, llm_agent, llm_intent
from whisperwick.memory import Memories
from whisperwick.memory_text import describe, importance_of
from whisperwick.world import World


def do(actor, action, **kw):
    return {"actor": actor, "action": action, **kw}


def hal_with_victor():
    """Victor walks to the Town Hall, so Hal can reach him."""
    w = fresh_world()
    assert w.move("npc_victor", "loc_town_hall").ok
    return w


def held_victor():
    w = hal_with_victor()
    assert w.act(do("npc_hal", "arrest", target="npc_victor")).ok
    return w


def assert_rejected(w, intent, text):
    before = w.state_hash()
    r = w.act(intent)
    assert not r.ok and text in r.reason
    assert w.state_hash() == before  # nothing changed, not even the log


# ---- arrest: every reject reason ----------------------------------------------


def test_scenario_names_hal_as_authority():
    assert fresh_world().authority == ["npc_hal"]


def test_non_authority_villager_cannot_arrest():
    w = hal_with_victor()
    assert_rejected(w, do("npc_victor", "arrest", target="npc_hal"), "no authority")


def test_player_cannot_arrest():
    w = fresh_world()
    assert_rejected(w, do("player", "arrest", target="npc_victor"), "no authority")


def test_held_authority_cannot_arrest():
    w = hal_with_victor()
    w.npcs["npc_hal"].held_by = "npc_hal"  # forced state: authority held by authority
    assert_rejected(w, do("npc_hal", "arrest", target="npc_victor"), "being held")


def test_arrest_unknown_target():
    assert_rejected(fresh_world(), do("npc_hal", "arrest", target="npc_nobody"), "unknown npc")


def test_arrest_no_target():
    assert_rejected(fresh_world(), do("npc_hal", "arrest"), "unknown npc")


def test_cannot_arrest_yourself():
    assert_rejected(fresh_world(), do("npc_hal", "arrest", target="npc_hal"), "yourself")


def test_cannot_arrest_the_dead():
    assert_rejected(fresh_world(), do("npc_hal", "arrest", target="npc_mayor"), "dead")


def test_cannot_arrest_someone_elsewhere():
    assert_rejected(fresh_world(), do("npc_hal", "arrest", target="npc_victor"), "not here")


def test_cannot_arrest_someone_already_held():
    w = held_victor()
    assert_rejected(w, do("npc_hal", "arrest", target="npc_victor"), "already held")


# ---- arrest: success ----------------------------------------------------------


def test_arrest_sets_custody_and_logs_event_with_witnesses():
    w = hal_with_victor()
    assert w.move("npc_bob", "loc_town_hall").ok
    r = w.act(do("npc_hal", "arrest", target="npc_victor"))
    assert r.ok
    assert w.npcs["npc_victor"].held_by == "npc_hal"
    e = r.event
    assert (e.type, e.actor, e.location) == ("arrest", "npc_hal", "loc_town_hall")
    assert e.data == {"target": "npc_victor"}
    # Everyone else present sees it, the target included. The dead mayor does not.
    assert e.witnesses == ["npc_bob", "npc_victor"]


# ---- release ------------------------------------------------------------------


def test_release_frees_and_logs():
    w = held_victor()
    r = w.act(do("npc_hal", "release", target="npc_victor"))
    assert r.ok and w.npcs["npc_victor"].held_by is None
    assert (r.event.type, r.event.data, r.event.witnesses) == (
        "release", {"target": "npc_victor"}, ["npc_victor"],
    )  # fmt: skip


def test_release_needs_authority():
    w = held_victor()
    assert_rejected(w, do("npc_victor", "release", target="npc_victor"), "no authority")
    assert_rejected(w, do("player", "release", target="npc_victor"), "no authority")


def test_release_unknown_or_free_target():
    w = hal_with_victor()
    assert_rejected(w, do("npc_hal", "release", target="npc_nobody"), "unknown npc")
    assert_rejected(w, do("npc_hal", "release", target="npc_victor"), "not held")


def test_release_needs_same_place():
    w = held_victor()
    w.npcs["npc_victor"].location = "loc_market"  # forced: held people cannot walk
    assert_rejected(w, do("npc_hal", "release", target="npc_victor"), "not here")


# ---- what a held person can and cannot do -------------------------------------


def test_held_person_cannot_move_take_drop_or_give():
    w = held_victor()
    w.npcs["npc_victor"].location = "loc_town_hall"
    held = "you are being held by npc_hal"
    assert_rejected(w, do("npc_victor", "move", target="loc_market"), held)
    assert_rejected(w, do("npc_victor", "take", item="item_knife"), held)
    assert_rejected(w, do("npc_victor", "drop", item="item_boots"), held)
    assert_rejected(w, do("npc_victor", "give", item="item_boots", target="npc_hal"), held)


def test_held_person_can_talk_look_and_show():
    w = held_victor()
    assert w.act(do("npc_victor", "talk", target="npc_hal", message="I am innocent")).ok
    assert w.act(do("npc_victor", "look")).ok
    assert w.act(do("npc_victor", "show", item="item_boots", target="npc_hal")).ok


def test_look_lists_held_people():
    w = held_victor()
    assert w.act(do("npc_hal", "look")).observation["held"] == ["npc_victor"]


def test_released_person_can_move_again():
    w = held_victor()
    assert w.act(do("npc_hal", "release", target="npc_victor")).ok
    assert w.move("npc_victor", "loc_market").ok


# ---- save and load ------------------------------------------------------------


def test_custody_survives_save_and_load():
    w = held_victor()
    loaded = World.from_dict(json.loads(json.dumps(w.to_dict())))
    assert loaded.npcs["npc_victor"].held_by == "npc_hal"
    assert loaded.authority == ["npc_hal"]
    assert loaded.state_hash() == w.state_hash()


def test_custody_is_part_of_the_state_hash():
    a, b = hal_with_victor(), held_victor()
    assert a.state_hash() != b.state_hash()


# ---- memory text --------------------------------------------------------------


def test_memory_text_by_point_of_view():
    w = held_victor()
    e = w.log.all()[-1]
    assert "Hal (npc_hal) arrested Victor (npc_victor)" in describe(e, w, "npc_bob")
    assert "You were arrested by Hal (npc_hal)" in describe(e, w, "npc_victor")
    assert "You arrested Victor (npc_victor)" in describe(e, w, "npc_hal")
    assert [importance_of(e, v) for v in ("npc_hal", "npc_victor", "npc_bob")] == [9, 9, 8]


def test_witnesses_remember_the_arrest():
    w = held_victor()
    memories = Memories()
    memories.observe(w.log.all()[-1], w)
    assert memories["npc_victor"].memories[0].importance == 9


# ---- LLM side -----------------------------------------------------------------


def test_schema_offers_arrest_only_to_authority():
    w = fresh_world()
    hal = llm_agent.intent_schema(w, "npc_hal")["properties"]["action"]["enum"]
    bob = llm_agent.intent_schema(w, "npc_bob")["properties"]["action"]["enum"]
    assert "arrest" in hal and "release" in hal
    assert "arrest" not in bob and "release" not in bob
    assert bob == llm_intent.ACTIONS


def prompt(w, npc):
    return llm_agent.build_messages(w, npc)[0]["content"]


def test_prompt_states_facts_for_everyone_and_the_guard():
    w = fresh_world()
    assert belief_text.WORDS_RULE in prompt(w, "npc_bob")
    assert "you can hold someone with the arrest action" not in prompt(w, "npc_bob")
    hal = prompt(w, "npc_hal")
    assert "As the guard, you can hold someone with the arrest action" in hal
    assert "Saying someone is under arrest does nothing by itself." in hal


def test_prompt_shows_custody():
    w = held_victor()
    assert "You are being held by Hal. You cannot move, take, drop or give." in prompt(
        w, "npc_victor"
    )
    assert "npc_victor (Victor, merchant, held by Hal)" in prompt(w, "npc_hal")


# ---- bad scenario data fails loudly -------------------------------------------


def test_setup_refuses_unknown_authority():
    w = fresh_world()
    with pytest.raises(ValueError):
        World(list(w.locations.values()), list(w.npcs.values()), w.clock, w.log,
              authority=["npc_ghost"])  # fmt: skip


def test_arrest_with_reason_logs_it_and_witnesses_remember_it():
    w = hal_with_victor()
    r = w.act(do("npc_hal", "arrest", target="npc_victor", message=" for the knife "))
    assert r.ok and r.event.data == {"target": "npc_victor", "reason": "for the knife"}
    text = describe(r.event, w, "npc_hal")
    assert text.endswith('arrested Victor (npc_victor), saying: "for the knife"')
    assert 'You were arrested by Hal (npc_hal), saying: "for the knife"' in describe(
        r.event, w, "npc_victor"
    )


def test_arrest_without_message_has_no_reason_key():
    for message in (None, "", "   "):
        w = hal_with_victor()
        r = w.act(do("npc_hal", "arrest", target="npc_victor", message=message))
        assert r.ok and r.event.data == {"target": "npc_victor"}
        assert "saying" not in describe(r.event, w, "npc_hal")


def test_too_long_reason_is_rejected_and_changes_nothing():
    w = hal_with_victor()
    long = "x" * 501
    assert_rejected(w, do("npc_hal", "arrest", target="npc_victor", message=long), "longer than")
    assert w.npcs["npc_victor"].held_by is None
    w = held_victor()
    assert_rejected(w, do("npc_hal", "release", target="npc_victor", message=long), "longer than")
    assert w.npcs["npc_victor"].held_by == "npc_hal"


def test_release_with_reason():
    w = held_victor()
    r = w.act(do("npc_hal", "release", target="npc_victor", message="no proof"))
    assert r.ok and r.event.data["reason"] == "no proof"
    text = describe(r.event, w, "npc_hal")
    assert text.endswith('released Victor (npc_victor), saying: "no proof"')


def test_outcome_shows_the_reason_of_the_final_arrest():
    from whisperwick import outcome

    w = hal_with_victor()
    w.act(do("npc_hal", "arrest", target="npc_victor", message="obstruction"))
    text = outcome.format_outcome(w.log.all(), {})
    assert 'saying: "obstruction"' in text
    assert 'Reason given for holding npc_victor: "obstruction"' in text


def test_authority_prompt_mentions_message_as_reason():
    w = fresh_world()
    assert "reason" in " ".join(belief_text.custody_lines(w, "npc_hal"))
    assert "reason" not in " ".join(belief_text.custody_lines(w, "npc_bob"))
