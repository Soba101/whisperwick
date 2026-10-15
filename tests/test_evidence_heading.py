"""Starting evidence is shown under its own heading in every prompt that lists memories (#56)."""

from helpers import fresh_world

from whisperwick import interview, llm_agent, thinking, thought_prompt
from whisperwick.memory import MemoryStream

HEAD = "What you knew before today:"


def stream_with_evidence():
    s = MemoryStream()
    s.add(0, "I killed the mayor.", 9, "evidence")
    s.add(60, "Bob said hello", 5)
    return s


def split_lines(text):
    return text.split("\n")


def test_act_prompt_has_heading_then_ordinary_memories():
    world = fresh_world()
    evidence, others = llm_agent.memory_parts(stream_with_evidence(), 100, world, "npc_victor")
    text = llm_agent.build_messages(world, "npc_victor", others, evidence=evidence)[0]["content"]
    lines = split_lines(text)
    i = lines.index(HEAD)
    assert lines[i + 1] == "- I killed the mayor."
    assert lines[i + 2 :][:2] == ["You remember:", "- Bob said hello"]


def test_no_evidence_means_no_heading():
    world = fresh_world()
    text = llm_agent.build_messages(world, "npc_bob", ["Bob said hello"])[0]["content"]
    assert HEAD not in text and "You remember:" in text
    only = llm_agent.build_messages(world, "npc_bob", [], evidence=["x"])[0]["content"]
    assert HEAD in only and "You remember:" not in only


def test_interview_prompt_has_heading():
    world = fresh_world()
    text = interview.messages(world, "npc_victor", stream_with_evidence())[0]["content"]
    lines = split_lines(text)
    i = lines.index(HEAD)
    assert lines[i + 1] == "- I killed the mayor."
    assert lines[i + 2] == "You remember:"
    plain = MemoryStream()
    plain.add(60, "Bob said hello", 5)
    assert HEAD not in interview.messages(world, "npc_victor", plain)[0]["content"]


def test_thought_prompt_groups_but_keeps_ids():
    world = fresh_world()
    shown = thinking.shown_memories(stream_with_evidence())
    text = thought_prompt.messages(world, "npc_victor", None, shown, None)[0]["content"]
    lines = split_lines(text)
    i = lines.index("What you knew before today, each with its id:")
    assert lines[i + 1] == "[m0] I killed the mayor."
    assert lines[i + 2] == "Your memories, each with its id:"
    assert lines[i + 3] == "[m1] Bob said hello"
    plain = MemoryStream()
    plain.add(60, "Bob said hello", 5)
    shown = thinking.shown_memories(plain)
    out = thought_prompt.messages(world, "npc_victor", None, shown, None)[0]["content"]
    assert "before today" not in out
