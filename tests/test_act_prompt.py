"""Keep the act prompt identical to the Week 7 render before the reuse reorder."""

from pathlib import Path

from helpers import fresh_world

from whisperwick.act_prompt import build_messages
from whisperwick.made_prompt import ACTION_TEXT


def test_prompt_matches_pre_reuse_render_exactly():
    # Compare the whole text: the same words in a different order change behaviour.
    original = Path(__file__).with_name("fixtures") / "act_prompt_before_reuse.txt"
    messages = build_messages(
        fresh_world(), "npc_hal", ["Bob said hello."], feedback="npc_x is not here",
        personality="Patient.",
        belief={"suspect": None, "thoughts": "I need facts.", "trust": []},
        private_lines=["Private notebook:", "- Check the market."],
        evidence=["I saw the mayor."],
    )
    # This is the only new action text; every other prompt byte stays the same.
    action_line = next(line for line in messages[0]["content"].splitlines()
                       if line.startswith("Actions:"))
    additions = " use (item = an item id)." + ACTION_TEXT
    assert action_line == next(line for line in original.read_text().splitlines()
                               if line.startswith("Actions:")) + additions
    messages[0]["content"] = messages[0]["content"].replace(additions, "")
    assert messages == [
        {"role": "system", "content": original.read_text()},
        {"role": "user", "content": "What do you do now?"},
    ]
