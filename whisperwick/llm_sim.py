"""The run loop for LLM agents. (sim.py stays the stub loop.)

Each minute the scheduler picks who gets a model call. Everyone else waits.
"""

from collections.abc import Callable

from whisperwick import llm_agent, memory, thinking
from whisperwick.belief_log import BeliefLog
from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.memory import Memories
from whisperwick.player import PLAYER_ID, PlayerSource
from whisperwick.player_turn import apply_player_turn
from whisperwick.repeat_guard import ActionHistory
from whisperwick.scheduler import SLEEP_START, Scheduler
from whisperwick.world import World

# Villagers think every 4 game hours while awake, and again at bedtime.
THINK_EVERY = 240


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
    # Optional human or script playing the player. None = the player stays idle.
    player: PlayerSource | None = None,
    # Character text per villager: npc id -> personality. Shown in prompts. Optional.
    personalities: dict[str, str] | None = None,
    # Where thoughts are kept. None = an in-memory log that the caller never sees.
    belief_log: BeliefLog | None = None,
) -> tuple[Memories, dict]:
    """Run the world for some minutes. Returns the memories and the stats."""
    memories = memories if memories is not None else Memories()
    stats = stats if stats is not None else {}
    # Only the living are scheduled or think. The dead never get a model call.
    # The player is left out too: no model calls, no memory stream, no thinking.
    living = sorted(n for n in world.npcs if world.npcs[n].alive and n != PLAYER_ID)
    scheduler = Scheduler(living)
    personalities = personalities or {}
    belief_log = belief_log if belief_log is not None else BeliefLog()
    # What NPCs did this run, for the repeat guard. Agent side only, never world state.
    history = ActionHistory()
    # Private starting knowledge goes in before the first turn.
    if evidence:
        memory.seed_evidence(memories, evidence, world.clock.tick)
    for _ in range(minutes):
        tick = world.clock.tick
        # The player goes first, even at night, so NPCs react to them this same minute.
        if player and not apply_player_turn(world, player, memories, scheduler, stats):
            break  # the player quit
        # NPCs act one by one, not all at once. A later NPC sees what an earlier one did
        # this same minute. Order is sorted ids, so it is still deterministic
        # for a given model output.
        for npc in scheduler.due(tick):
            lines = llm_agent.memory_lines(memories[npc], tick, world, npc)
            result = llm_agent.act(
                world, npc, client, lines, stats,
                personalities.get(npc), belief_log.latest(npc), history,
            )  # fmt: skip
            scheduler.acted(npc, tick)
            if result.event:
                # Remember right away, before anyone else moves (see Memories.observe).
                memories.observe(result.event, world)
                scheduler.notice(result.event)
            if result.observation:
                memories.observe_look(npc, result.observation, tick, world)
        world.clock.advance()
        # Thinking time: every 4 awake hours, and at bedtime. Never in the night.
        now = world.clock.tick
        bedtime = now % MINUTES_PER_DAY == SLEEP_START * 60
        if bedtime or (now % THINK_EVERY == 0 and not scheduler.asleep(now)):
            # Sorted ids, so the order of model calls (and the log) is the same every run.
            for npc in living:
                if thinking.think(
                    memories[npc], npc, world, client, now,
                    personalities.get(npc), belief_log, stats,
                ):  # fmt: skip
                    stats["thoughts"] = stats.get("thoughts", 0) + 1
        # Reported last, so the hour's thoughts are already in the stats.
        if on_hour and world.clock.tick % 60 == 0:
            on_hour(world, stats)
    return memories, stats
