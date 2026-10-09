"""LLM run loop tests. A fake client stands in for the model: no network, ever."""

from helpers import SCENARIO, fresh_world

from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.llm_sim import run_llm
from whisperwick.scenario import build_world, load_scenario

LOOK = {"action": "look", "target": None, "message": None}


class LookClient:
    """Always looks; answers a reflection schema with a fixed thought. Counts calls."""

    def __init__(self):
        self.intent_calls = 0
        self.reflect_calls = 0

    def chat(self, messages, schema):
        if "thoughts" in schema["properties"]:
            self.reflect_calls += 1
            return {"thoughts": "all quiet"}
        self.intent_calls += 1
        return dict(LOOK)


def test_two_hours_make_one_call_per_npc_per_hour():
    world = fresh_world()
    client, stats = LookClient(), {}
    run_llm(world, client, 120, stats=stats)
    # Start is 08:00. Everyone decides at 08:00 and again at 09:00.
    # The dead mayor gets no turns, so count only the living.
    living = [n for n in world.npcs.values() if n.alive]
    assert client.intent_calls == 2 * len(living) == stats["calls"]
    assert world.clock.label() == "day 1 10:00"


def test_clock_advances_by_minutes():
    world = fresh_world()
    start = world.clock.tick
    run_llm(world, LookClient(), 37)
    assert world.clock.tick == start + 37


def test_talk_reply_gives_the_target_a_memory():
    world = fresh_world()
    # Bob and Victor share the market. Only Bob talks; everyone else just looks.
    talk = {"action": "talk", "target": "npc_victor", "message": "Knife sale today?"}

    class BobTalks(LookClient):
        def chat(self, messages, schema):
            if "(npc_bob)" in messages[0]["content"]:
                return talk
            return super().chat(messages, schema)

    memories, _ = run_llm(world, BobTalks(), 1)
    assert any("Knife sale" in m.text for m in memories["npc_victor"].memories)
    assert any("Knife sale" in m.text for m in memories["npc_bob"].memories)


def test_a_full_day_reflects_once_per_npc():
    world = fresh_world()
    client, stats = LookClient(), {}
    memories, _ = run_llm(world, client, MINUTES_PER_DAY, stats=stats)
    living = [n for n in world.npcs if world.npcs[n].alive]
    assert client.reflect_calls == stats["reflections"] == len(living)
    for npc in living:
        # Later morning looks come after it, so look for it anywhere in the stream.
        assert [m.kind for m in memories[npc].memories].count("reflection") == 1


def test_looking_changes_nothing_but_the_clock():
    a, b = fresh_world(), fresh_world()
    run_llm(a, LookClient(), 180)
    b.clock.advance(180)  # the only change a look-only run may make
    assert a.state_hash() == b.state_hash()


def test_evidence_is_seeded_and_the_dead_never_act():
    scenario = load_scenario(SCENARIO)
    world = build_world(scenario)
    client = LookClient()
    memories, _ = run_llm(world, client, 1, evidence=scenario.evidence)
    assert any("killed Mayor Aldric" in m.text for m in memories["npc_victor"].memories)
    assert "npc_mayor" not in memories  # no turn, no memories, no reflection
    assert client.intent_calls == 5
