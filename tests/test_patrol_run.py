"""Patrol inside the LLM run loop. A fake client stands in for the model: no network."""

from helpers import fresh_world
from test_llm_sim import LookClient

from whisperwick.llm_sim import run_llm


def test_patrol_in_the_run_loop_gives_hal_no_turns_for_the_hour():
    world = fresh_world()
    hal_calls = []  # clock ticks at which Hal was asked to act

    class HalPatrols(LookClient):
        def chat(self, messages, schema):
            # Other prompts mention Hal in "People here", so match the opening line.
            hal = messages[0]["content"].startswith("You are Hal (npc_hal)")
            if hal and "thoughts" not in schema["properties"]:
                hal_calls.append(world.clock.tick)
                if len(hal_calls) == 1:
                    return {"action": "patrol", "target": None, "message": None}
            return super().chat(messages, schema)

    start = world.clock.tick
    memories, _ = run_llm(world, HalPatrols(), 130)
    # Asked at the start, then not again until the hour is up.
    assert hal_calls[0] == start and hal_calls[1] == start + 60
    hops = [e for e in world.log.all() if e.type == "move" and e.data.get("patrol")]
    assert [e.tick - start for e in hops] == [15, 30, 45]
    # Alice is at the inn, the second stop: she witnessed that hop and remembers it.
    assert "npc_alice" in hops[1].witnesses
    assert any("Hal" in m.text for m in memories["npc_alice"].memories)
