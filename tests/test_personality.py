"""Scenario personalities: they load, they are checked, and the scenario has the five."""

import pytest
from helpers import SCENARIO

from whisperwick.scenario import Scenario, build_world, load_scenario

TEXTS = {
    "npc_alice": "Warm and chatty, and loves to hear the latest news. Trusts her regulars "
    "quickly and strangers slowly. Hates trouble in her inn.",
    "npc_bob": "Blunt and stubborn. Trusts what he sees with his own eyes far more than talk. "
    "Little patience for gossip.",
    "npc_sarah": "Calm and careful. Wants proof before she accuses anyone, and believes "
    "everyone deserves a fair hearing.",
    "npc_hal": "Dutiful and proud of his post. Wary of newcomers, and of anyone who tells him "
    "how to do his job.",
    "npc_victor": "Charming, clever and calculating. Good at telling people what they want to "
    "hear. Protects his reputation above all.",
}


def test_scenario_has_the_five_personalities():
    assert load_scenario(SCENARIO).personality == TEXTS


def test_personality_is_optional():
    sc = load_scenario(SCENARIO)
    sc.personality = {}
    build_world(sc)  # no error


def test_personality_for_an_unknown_npc_fails_loudly():
    sc = load_scenario(SCENARIO)
    sc.personality = {"npc_victer": "Charming."}
    with pytest.raises(ValueError, match="personality given to unknown npc npc_victer"):
        build_world(sc)


def test_formula_sections_are_gone_from_the_scenario():
    fields = Scenario.model_fields
    for removed in ("trust", "clues", "beliefs", "goals"):
        assert removed not in fields
