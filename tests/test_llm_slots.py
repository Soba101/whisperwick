"""Slots are optional, deterministic and used only for act calls. No network."""

import json

import pytest
from helpers import SCENARIO, fresh_world
from test_llama_server_client import MESSAGES, SCHEMA, fake_urlopen, reply
from test_llm_sim import LOOK, LookClient
from test_recall import private_for, recall_reply, stream

from whisperwick import llm_agent, llm_cli, settings
from whisperwick.interview import interview
from whisperwick.llm_client import FakeClient, LlamaServerClient, OllamaClient
from whisperwick.llm_sim import run_llm
from whisperwick.memory import Memories
from whisperwick.scenario import load_scenario


@pytest.mark.parametrize("slot", [None, 0, 3])
def test_request_slot_fields_only_when_given(monkeypatch, slot):
    seen = fake_urlopen(monkeypatch, reply('{"action": "look"}'))
    LlamaServerClient("http://unused/v1", "m").chat(MESSAGES, SCHEMA, slot=slot)
    body = json.loads(seen["request"].data)
    if slot is None:
        assert "id_slot" not in body and "cache_prompt" not in body
    else:
        assert body["id_slot"] == slot and body["cache_prompt"] is True


def test_settings_default_file_override_and_invalid_values(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.delenv("LLM_SLOTS", raising=False)
    assert settings.llm_slots(path) is None
    path.write_text("LLM_SLOTS=5\n")
    assert settings.llm_slots(path) == 5
    monkeypatch.setenv("LLM_SLOTS", "2")
    assert settings.llm_slots(path) == 2
    for bad in ("0", "-1", "two", "1.5"):
        monkeypatch.setenv("LLM_SLOTS", bad)
        with pytest.raises(ValueError, match="LLM_SLOTS"):
            settings.llm_slots(path)


class SlotClient(LookClient):
    def __init__(self):
        super().__init__()
        self.slots = []

    def chat(self, messages, schema, **kwargs):
        self.slots.append((messages[0]["content"].splitlines()[0], kwargs))
        return super().chat(messages, schema)


@pytest.mark.parametrize("slots", [2, 5])
def test_mapping_uses_sorted_living_villagers_and_thinking_has_no_slot(slots):
    world, client = fresh_world(), SlotClient()
    # Reverse insertion order to prove slots come from sorted ids.
    world.npcs = dict(reversed(list(world.npcs.items())))
    living = sorted(n for n, person in world.npcs.items() if person.alive and n != "player")
    run_llm(world, client, 240, slots=slots, agent_memory=False)
    expected = {n: i % slots for i, n in enumerate(living)}
    for i, (identity, kwargs) in enumerate(client.slots[:5]):
        assert f"({living[i]})" in identity
        assert kwargs == {"slot": expected[living[i]]}
    assert len(client.slots) == 25  # four act rounds and one thinking round
    assert all(kwargs == {} for _, kwargs in client.slots[-5:])
    assert [kw for _, kw in client.slots[:5]] == [kw for _, kw in client.slots[5:10]]


def test_unset_slots_preserve_two_argument_client_calls():
    client = SlotClient()
    run_llm(fresh_world(), client, 1)
    assert len(client.slots) == 5
    assert all(kwargs == {} for _, kwargs in client.slots)


def test_slot_survives_recall_and_rejection_retry():
    class RecordingFake(FakeClient):
        def chat(self, messages, schema, **kwargs):
            slots.append(kwargs)
            return super().chat(messages, schema, **kwargs)

    slots = []
    client = RecordingFake([
        recall_reply("knife"),
        {"action": "move", "target": "loc_unknown"},
        LOOK,
    ])
    assert llm_agent.act(
        fresh_world(), "npc_bob", client, private=private_for(stream()), slot=0
    ).ok
    assert slots == [{"slot": 0}] * 3


def test_ollama_ignores_slot(monkeypatch):
    seen = fake_urlopen(monkeypatch, {"message": {"content": "{}"}})
    OllamaClient("http://unused/v1", "m").chat(MESSAGES, SCHEMA, slot=2)
    body = json.loads(seen["request"].data)
    assert "id_slot" not in body and "cache_prompt" not in body


def test_interviews_do_not_request_a_slot():
    class InterviewClient:
        def chat(self, messages, schema, **kwargs):
            assert kwargs == {}
            return {"suspect": None, "why": "Unsure."}

    assert interview(fresh_world(), Memories(), InterviewClient(), ["npc_bob"]) == {
        "npc_bob": {"suspect": None, "why": "Unsure."}
    }


@pytest.mark.parametrize("slots", [None, 2])
def test_cli_reads_and_passes_slot_setting(monkeypatch, tmp_path, slots):
    monkeypatch.setattr(settings, "llm_base_url", lambda: "http://unused/v1")
    monkeypatch.setattr(settings, "llm_model", lambda: "m")
    monkeypatch.setattr(settings, "llm_server", lambda: "llama-server")
    monkeypatch.setattr(settings, "parallel", lambda: 1)
    monkeypatch.setattr(settings, "agent_memory", lambda: False)
    monkeypatch.setattr(settings, "llm_slots", lambda: slots)
    monkeypatch.setattr(llm_cli, "make_client", lambda *args: FakeClient([]))
    seen = {}

    def run(world, client, minutes, **kwargs):
        seen.update(kwargs)
        return Memories(), kwargs["stats"]

    monkeypatch.setattr(llm_cli, "run_llm", run)
    monkeypatch.setattr(llm_cli.run_report, "after_run", lambda *args: {"interview": {}})
    llm_cli.run_with_llm(load_scenario(SCENARIO), SCENARIO, str(tmp_path / "x.db"), 1, 0)
    assert seen["slots"] == slots
