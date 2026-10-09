"""The run loop for LLM agents. (sim.py stays the stub loop.)

Each minute the scheduler picks who gets a model call. Everyone else waits.
"""

from collections.abc import Callable

from whisperwick import llm_agent, memory
from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.memory import Memories
from whisperwick.scheduler import SLEEP_START, Scheduler
from whisperwick.world import World


def run_llm(
    world: World,
    client,
    minutes: int,
    memories: Memories | None = None,
    stats: dict | None = None,
    evidence: dict[str, list[str]] | None = None,
    # Optional hook, called with (world, stats) after each full game hour.
    # The CLI uses it to print progress. Tests can ignore it.
    on_hour: Callable[[World, dict], None] | None = None,
) -> tuple[Memories, dict]:
    """Run the world for some minutes. Returns the memories and the stats."""
    memories = memories if memories is not None else Memories()
    stats = stats if stats is not None else {}
    # Only the living are scheduled or reflect. The dead never get a model call.
    living = sorted(n for n in world.npcs if world.npcs[n].alive)
    scheduler = Scheduler(living)
    # Private starting knowledge goes in before the first turn.
    if evidence:
        memory.seed_evidence(memories, evidence, world.clock.tick)
    for _ in range(minutes):
        tick = world.clock.tick
        # NPCs act one by one, not all at once. A later NPC sees what an earlier one did
        # this same minute. Order is sorted ids, so it is still deterministic
        # for a given model output.
        for npc in scheduler.due(tick):
            lines = llm_agent.memory_lines(memories[npc], tick, world, npc)
            result = llm_agent.act(world, npc, client, lines, stats)
            scheduler.acted(npc, tick)
            if result.event:
                # Remember right away, before anyone else moves (see Memories.observe).
                memories.observe(result.event, world)
                scheduler.notice(result.event)
            if result.observation:
                memories.observe_look(npc, result.observation, tick)
        world.clock.advance()
        # When the clock reaches bedtime, each NPC sums up its day, in sorted order.
        if world.clock.tick % MINUTES_PER_DAY == SLEEP_START * 60:
            for npc in living:
                if memory.reflect(memories[npc], world.npcs[npc].name, client, world.clock.tick):
                    stats["reflections"] = stats.get("reflections", 0) + 1
        # Reported last, so the hour's reflections are already in the stats.
        if on_hour and world.clock.tick % 60 == 0:
            on_hour(world, stats)
    return memories, stats
