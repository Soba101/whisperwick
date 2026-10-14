"""Prompt reuse keeps the same words while moving changing facts to the end."""

from collections import Counter
from pathlib import Path

from helpers import fresh_world

from whisperwick import belief_text, llm_agent
from whisperwick.actions import Intent
from whisperwick.repeat_guard import ActionHistory


def fixture_messages(world, thoughts="I need facts."):
    return llm_agent.build_messages(
        world, "npc_hal", ["Bob said hello."], feedback="npc_x is not here",
        personality="Patient.",
        belief={"suspect": None, "thoughts": thoughts, "trust": []},
        private_lines=["Private notebook:", "- Check the market."],
        evidence=["I saw the mayor."],
    )


def test_every_original_line_is_preserved():
    # Captured before the reorder, so changed or missing words fail this check.
    original = Path(__file__).with_name("fixtures") / "act_prompt_before_reuse.txt"
    messages = fixture_messages(fresh_world())
    assert Counter(messages[0]["content"].splitlines()) == Counter(
        original.read_text().splitlines()
    )
    assert messages[1] == {"role": "user", "content": "What do you do now?"}


def test_stable_prefix_survives_new_time_place_belief_and_custody():
    world = fresh_world()
    before = fixture_messages(world)[0]["content"].splitlines()
    world.clock.advance(71)
    world.npcs["npc_hal"].location = "loc_market"
    world.npcs["npc_bob"].held_by = "npc_hal"
    after = fixture_messages(world, thoughts="I have a new belief.")[0]["content"].splitlines()
    n = before.index("What you think right now: you don't suspect anyone of anything yet. "
                     "I need facts.")
    assert n == 10
    assert before[:n] == after[:n]
    assert before[n:] != after[n:]
    assert before.index("Private notebook:") < before.index("Time: day 1 08:00.")
    assert after.index("You are holding: Bob (npc_bob) at Market.") > n
    assert after[-1] == "Your last action was rejected: npc_x is not here. Choose again."


def test_changing_lines_follow_the_requested_order():
    world = fresh_world()
    world.npcs["npc_bob"].location = "loc_town_hall"
    history = ActionHistory()
    history.record(world.clock.tick, Intent(
        actor="npc_hal", action="talk", target="npc_bob", message="Hello."
    ))
    lines = llm_agent.build_messages(
        world, "npc_hal", ["A memory."], history=history,
        private_lines=["A notebook line."], evidence=["Starting evidence."],
    )[0]["content"].splitlines()
    prefixes = [
        "You are Hal", "Reply only", "Only claim", "Actions:", belief_text.WORDS_RULE,
        "As the", belief_text.CLAIM_RULE, "What you knew", "- Starting evidence.",
        "A notebook line.", "Time:", "You are at", "Exits:", "People here:",
        "Items on", "You carry:", "Lying dead", "Your last words here:", "- told",
        "You remember:", "- A memory.",
    ]
    assert len(lines) == len(prefixes)
    assert all(line.startswith(prefix) for line, prefix in zip(lines, prefixes, strict=True))


def test_held_villager_status_is_late_and_keeps_its_words():
    world = fresh_world()
    world.npcs["npc_bob"].held_by = "npc_hal"
    lines = llm_agent.build_messages(world, "npc_bob", evidence=["A fact."])[0]["content"]
    status = "You are being held by Hal. You cannot move, take, drop or give."
    assert lines.index("- A fact.") < lines.index(status) < lines.index("Time:")
