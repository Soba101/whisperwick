"""LLM run loop tests. A fake client stands in for the model: no network, ever."""

from helpers import SCENARIO, fresh_world

from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.llm_sim import run_llm
from whisperwick.scenario import build_world, load_scenario

LOOK = {"action": "look", "target": None, "message": None}


class LookClient:
    """Always looks; answers a thinking schema with a fixed thought. Counts calls."""

    def __init__(self):
        self.intent_calls = 0
        self.think_calls = 0

    def chat(self, messages, schema):
        if "thoughts" in schema["properties"]:
            self.think_calls += 1
            return {"thoughts": "all quiet", "suspect": None, "sureness": "unsure",
                    "because": [], "trust": []}  # fmt: skip
        self.intent_calls += 1
        return dict(LOOK)


def test_two_hours_make_one_call_per_npc_per_hour():
    world = fresh_world()
    client, stats = LookClient(), {}
    run_llm(world, client, 120, stats=stats)
    # Start is 08:00. Everyone decides at 08:00 and again at 09:00.
    # The dead mayor gets no turns, so count only the living.
    living = [n for n in world.npcs.values() if n.alive and n.id != "player"]
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


def test_a_full_day_thinks_five_times_per_npc():
    world = fresh_world()
    client, stats = LookClient(), {}
    memories, _ = run_llm(world, client, MINUTES_PER_DAY, stats=stats)
    living = [n for n in world.npcs if world.npcs[n].alive and n != "player"]
    # From 08:00: 12:00, 16:00, 20:00, bedtime 22:00, then 08:00 next day. Not at 04:00 (asleep).
    assert client.think_calls == stats["thoughts"] == 5 * len(living)
    for npc in living:
        assert [m.kind for m in memories[npc].memories].count("reflection") == 5


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


def test_on_hour_is_called_once_per_game_hour():
    world = fresh_world()
    seen = []
    # Start is 08:00, so three hours end at 09:00, 10:00 and 11:00.
    run_llm(world, LookClient(), 180, on_hour=lambda w, s: seen.append(w.clock.label()))
    assert seen == ["day 1 09:00", "day 1 10:00", "day 1 11:00"]


class DeadServer:
    """Every call fails, like the PC dropping off the network (#34)."""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, schema):
        from whisperwick.llm_client import LLMError

        self.calls += 1
        raise LLMError("chat failed: No route to host")


def test_run_stops_when_the_model_server_is_gone():
    world, client, stats = fresh_world(), DeadServer(), {}
    start = world.clock.tick
    run_llm(world, client, 600, stats=stats)
    # It stops after 20 failed calls in a row, long before the 10 hours are up.
    assert "20 times in a row" in stats["stopped"] and "No route to host" in stats["stopped"]
    assert world.clock.tick - start < 600


def test_one_good_answer_resets_the_error_count():
    class Flaky(LookClient):
        """Fails 19 times, then answers once, then fails again. Never 20 in a row."""

        def __init__(self):
            super().__init__()
            self.n = 0

        def chat(self, messages, schema):
            from whisperwick.llm_client import LLMError

            self.n += 1
            if self.n % 20:
                raise LLMError("blip")
            return super().chat(messages, schema)

    stats = {}
    run_llm(fresh_world(), Flaky(), 120, stats=stats)
    assert "stopped" not in stats
