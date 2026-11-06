"""Patrol: an authority walks through every place in turn, taking one hour.

Registered in actions.HANDLERS (imported from the bottom of actions.py, so import
actions first, never this file on its own).

The world is physics only. Patrol is an ability, like arrest: nothing makes anyone
use it. The actor only returns the intent; the engine checks it and does the walking.

How it resolves (the clock only moves one minute at a time, so the walk is spread out):
- The start tick logs one "patrol" event, where the actor stands. The route is planned then.
- The actor stays in the first place for the first slot. Each later slot, World.step (or the
  LLM loop) calls advance_patrols, which makes one ordinary "move" event per hop. Those
  moves have the same witnesses and data as a normal move, so every move consumer works
  unchanged. The extra key "patrol": True only marks them.
- While the hour lasts the actor cannot act (it is walking). Being held or dying ends it.
"""

from whisperwick.actions import ActionResult, Intent, reject
from whisperwick.custody import _authority_problem
from whisperwick.events import Event

PATROL_MINUTES = 60


def plan_route(world, start: str) -> list[str]:
    """The hops of a patrol from `start`: always walk to the nearest place not seen yet.

    Breadth-first search over links, neighbours in sorted id order, so ties break the same
    way every time and no randomness is used. Every hop is a real link, so the walk obeys
    the same adjacency as a normal move. The route ends in the last place it reaches, which
    is where the actor then stands. Places that cannot be reached are left out.
    """
    seen = {start}
    here, route = start, []
    while True:
        # Search outwards from here for the nearest unseen place, remembering how we got there.
        came_from = {here: None}
        queue = [here]
        goal = None
        for place in queue:
            if place not in seen:
                goal = place
                break
            for nxt in sorted(world.locations[place].links):
                if nxt not in came_from:
                    came_from[nxt] = place
                    queue.append(nxt)
        if goal is None:
            return route
        path = []
        step = goal
        while step != here:
            path.append(step)
            step = came_from[step]
        # Walking through places already seen is fine; only the goal is new.
        route += reversed(path)
        seen.add(goal)
        here = goal


def patrol_problem(world, intent: Intent) -> str | None:
    """World.act calls this for every action: someone on patrol is busy walking."""
    patrol = world.patrols.get(intent.actor)
    if patrol is None:
        return None
    return f"you are on patrol for {patrol['until'] - world.clock.tick} more minutes"


def do_patrol(world, intent: Intent) -> ActionResult:
    """Start a one-hour walk through every place. Only a free authority may."""
    problem = _authority_problem(world, intent)
    if problem:
        return reject(problem)
    me = world.npcs[intent.actor]
    # (A held actor never gets here: World.act's custody check stops "patrol" first.)
    route = plan_route(world, me.location)
    if not route:
        return reject("there is nowhere to patrol")
    # One slot at the start place, then one per hop, so each place gets about the same time.
    slot = PATROL_MINUTES // (len(route) + 1)
    now = world.clock.tick
    world.patrols[me.id] = {
        "until": now + PATROL_MINUTES,
        "stops": [[now + slot * (i + 1), to] for i, to in enumerate(route)],
    }
    event = world.log.append(
        Event(
            tick=now,
            type="patrol",
            actor=me.id,
            location=me.location,
            data={"route": route, "minutes": PATROL_MINUTES},
            witnesses=[n for n in world.npcs_at(me.location) if n != me.id],
        )
    )
    return ActionResult(True, event=event)


def advance_patrols(world) -> list[Event]:
    """Make every hop that is due now and end finished patrols. Call after the clock moves.

    Returns the new move events, in actor-id order, so callers can tell memories and the
    scheduler about them exactly as they do for an action.
    """
    events = []
    for actor in sorted(world.patrols):
        patrol = world.patrols[actor]
        npc = world.npcs[actor]
        # Dying or being held ends the walk: the rest of the route is never made.
        if not npc.alive or npc.held_by is not None:
            del world.patrols[actor]
            continue
        while patrol["stops"] and patrol["stops"][0][0] <= world.clock.tick:
            _, to = patrol["stops"].pop(0)
            here = npc.location
            witnesses = sorted(set(world.npcs_at(here) + world.npcs_at(to)) - {actor})
            npc.location = to
            events.append(world.log.append(Event(
                tick=world.clock.tick,
                type="move",
                actor=actor,
                location=to,
                data={"from": here, "to": to, "patrol": True},
                witnesses=witnesses,
            )))
        if world.clock.tick >= patrol["until"]:
            del world.patrols[actor]
    return events
