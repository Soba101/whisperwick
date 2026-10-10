"""The run loop for LLM agents. (sim.py stays the stub loop.)

Each minute the scheduler picks who gets a model call. Everyone else waits.
"""

from collections.abc import Callable

from whisperwick import llm_agent, memory, thought_memory
from whisperwick.agent_log import AgentLog
from whisperwick.belief_log import BeliefLog
from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.memory import Memories
from whisperwick.notebook import Notebooks
from whisperwick.player import PLAYER_ID, PlayerSource
from whisperwick.player_turn import apply_player_turn
from whisperwick.recall import Private
from whisperwick.repeat_guard import ActionHistory
from whisperwick.scheduler import SLEEP_START, Scheduler
from whisperwick.world import World

# Villagers think every 4 game hours while awake, and again at bedtime.
THINK_EVERY = 240
# After this many failed model calls in a row the run stops (#34). In one run the PC
# dropped off the network and 247 calls failed while the villagers only looked around.
MAX_ERRORS_IN_A_ROW = 20


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
    # How many thinking calls may be in flight at once. 1 = one after another, as before.
    parallel: int = 1,
    # Week 6: villager recall and notebook. False = prompts and schemas as in week 5.
    agent_memory: bool = True,
    notebooks: Notebooks | None = None,  # kept by the caller to read at the end
    agent_log: AgentLog | None = None,  # recall searches, in memory if no path
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
    notebooks = notebooks if notebooks is not None else Notebooks()
    agent_log = agent_log if agent_log is not None else AgentLog()
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
                Private(memories[npc], notebooks, agent_log) if agent_memory else None,
            )  # fmt: skip
            scheduler.acted(npc, tick)
            if result.event:
                # Remember right away, before anyone else moves (see Memories.observe).
                memories.observe(result.event, world)
                scheduler.notice(result.event)
            if result.observation:
                memories.observe_look(npc, result.observation, tick, world)
        if stats.get("errors_in_a_row", 0) >= MAX_ERRORS_IN_A_ROW:
            # Stop instead of running on without a model. The caller still saves what exists.
            stats["stopped"] = f"model failed {MAX_ERRORS_IN_A_ROW} times in a row: " + str(
                stats.get("last_error", "")
            )
            break
        world.clock.advance()
        # Thinking time: every 4 awake hours, and at bedtime. Never in the night.
        now = world.clock.tick
        bedtime = now % MINUTES_PER_DAY == SLEEP_START * 60
        if bedtime or (now % THINK_EVERY == 0 and not scheduler.asleep(now)):
            # A thought only reads its own villager's memories, the villager's last belief
            # and the world (which does not change now). So the model calls can overlap.
            # Prepared and applied in sorted ids, so the result matches a one-by-one run.
            thought_memory.think_all(
                living, memories, world, client, personalities, belief_log, now, parallel,
                stats, notebooks if agent_memory else None, agent_log,
            )
        # Reported last, so the hour's thoughts are already in the stats.
        if on_hour and world.clock.tick % 60 == 0:
            on_hour(world, stats)
    return memories, stats
