"""The run loop for LLM agents. (sim.py stays the stub loop.)

Each minute the scheduler picks who gets a model call. Everyone else waits.
"""

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
) -> tuple[Memories, dict]:
    """Run the world for some minutes. Returns the memories and the stats."""
    memories = memories if memories is not None else Memories()
    stats = stats if stats is not None else {}
    scheduler = Scheduler(world.npcs)
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
            for npc in sorted(world.npcs):
                if memory.reflect(memories[npc], world.npcs[npc].name, client, world.clock.tick):
                    stats["reflections"] = stats.get("reflections", 0) + 1
    return memories, stats
