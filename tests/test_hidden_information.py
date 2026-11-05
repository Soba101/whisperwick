"""Hidden information: one villager's private channels never reach another villager's prompt.

A recording client stands in for the model (no network). It is given a whole short run, so
the checks go through the real code path: run_llm -> act / think prompts. A secret may only
travel by an in-world event (the positive control: Bob says it aloud).
"""

import json

import pytest
from helpers import fresh_world

from whisperwick import interview
from whisperwick.exchange_prompt import build_messages as exchange_messages
from whisperwick.llm_sim import run_llm
from whisperwick.web_state import you_view

SECRET = "SECRET-A-7f3q"
OWNER = "npc_bob"  # Bob holds the secret; he shares the market with Victor
LOOK = {"action": "look", "target": None, "message": None}
# One thinking reply per private channel the model can write to.
THOUGHT = {"suspect": None, "sureness": "unsure", "because": [], "trust": [], "recall": None}
CHANNELS = {
    "thoughts": {"thoughts": SECRET},
    "aim": {"aim": SECRET, "aim_status": "new"},
    "notebook_me": {"notebook_me": SECRET},
    "notebook_people": {"notebook_people": [{"person": "npc_hal", "line": SECRET}]},
    "suspect_reason": {"suspect": "npc_hal", "of_what": SECRET},
}


class Recorder:
    """Looks every turn. Keeps every prompt it was sent as (villager id, text)."""

    def __init__(self, thinks=None, says=None):
        self.thinks, self.says, self.prompts = thinks or {}, says, []

    def chat(self, messages, schema):
        text = "\n".join(m["content"] for m in messages)
        who = text.split("(")[1].split(")")[0]  # "You are Bob (npc_bob), ..."
        self.prompts.append((who, text))
        if "thoughts" in schema["properties"]:
            owner = who == OWNER
            return {**THOUGHT, "thoughts": "all quiet", **(self.thinks if owner else {})}
        if self.says and who == OWNER:
            return {"action": "talk", "target": "npc_victor", "message": self.says}
        return dict(LOOK)


def run(client, **kwargs):
    world = fresh_world()
    memories, _ = run_llm(world, client, 300, **kwargs)  # past the 12:00 thinking time
    return world, memories, client.prompts


def check_hidden(prompts):
    mine = [t for who, t in prompts if who == OWNER]
    others = [t for who, t in prompts if who != OWNER]
    assert others and mine
    assert not [t for t in others if SECRET in t], "secret reached another villager"
    return mine


@pytest.mark.parametrize("channel", CHANNELS)
def test_thinking_channels_stay_private(channel):
    world, memories, prompts = run(Recorder(thinks=CHANNELS[channel]))
    # Bob's own later prompts show it, so the channel really works.
    assert any(SECRET in t for t in check_hidden(prompts))
    # The end-of-run interview prompt for everyone else is clean too.
    for npc in world.npcs:
        if npc not in (OWNER, "player") and world.npcs[npc].alive:
            assert SECRET not in interview.messages(world, npc, memories[npc])[0]["content"]


def test_starting_evidence_stays_private():
    _, _, prompts = run(Recorder(), evidence={OWNER: [f"I hid {SECRET}."]})
    mine = check_hidden(prompts)
    assert any(SECRET in t for t in mine if "What you knew before today" in t)


def test_personality_stays_private():
    personalities = {OWNER: f"Patient. {SECRET}", "npc_victor": "Loud."}
    _, _, prompts = run(Recorder(), personalities=personalities)
    check_hidden(prompts)


def test_exchange_prompt_for_other_pairs_and_player_view_are_clean():
    world = fresh_world()
    personalities = {OWNER: SECRET, "npc_victor": "Loud."}
    # Alice and Victor never share an event with Bob's private text.
    text = exchange_messages(world, "npc_alice", "npc_victor", personalities)[0]["content"]
    assert SECRET not in text
    assert SECRET not in json.dumps(you_view(world))


def test_a_secret_said_aloud_reaches_the_listener_only():
    client = Recorder(says=f"Psst, {SECRET}")
    _, memories, prompts = run(client)
    # Victor is in the market and heard it: a world event put it in his memory.
    assert any(SECRET in m.text for m in memories["npc_victor"].memories)
    assert any(SECRET in t for who, t in prompts if who == "npc_victor")
    # Hal was in the town hall: he heard nothing.
    assert not any(SECRET in t for who, t in prompts if who == "npc_hal")
    assert not any(SECRET in m.text for m in memories["npc_hal"].memories)
