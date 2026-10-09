"""Plain-English text and importance for events, from one NPC's point of view.

Split out of memory.py to keep that file small. memory.py re-exports these names.
"""

from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.world import World

# Item events. Each pairs the event type with the verb used in the sentence.
ITEM_VERBS = {"take": "picked up", "drop": "dropped", "give": "gave", "show": "showed"}


def name_of(world: World, npc_id: str) -> str:
    """Display name plus id, e.g. 'Bob (npc_bob)'. The id is what the model must use."""
    npc = world.npcs.get(npc_id)
    return f"{npc.name} ({npc_id})" if npc else npc_id


def claim_text(event: Event, world: World) -> str:
    """e.g. ' [claim: Hal (npc_hal) is the killer]', or '' when the talk had no claim."""
    claim = event.data.get("claim")
    if not claim:
        return ""
    verdict = "the killer" if claim["kind"] == "killer" else "innocent"
    return f" [claim: {name_of(world, claim['subject'])} is {verdict}]"


def describe(event: Event, world: World, viewer_id: str) -> str:
    """One short line about an event, as the viewer would remember it."""
    when = Clock(event.tick).label().capitalize()
    prefix = f"{when} at {event.location}:"
    me = event.actor == viewer_id
    who = "You" if me else name_of(world, event.actor)
    if event.type == "talk":
        to = event.data["to"]
        target = "you" if to == viewer_id else name_of(world, to)
        return (
            f'{prefix} {who} said to {target}: "{event.data["message"]}"{claim_text(event, world)}'
        )
    if event.type == "move":
        if me:
            return f"{prefix} You walked to {event.data['to']}"
        # A witness who is now at the destination saw them arrive. Others saw them leave.
        if world.npcs[viewer_id].location == event.data["to"]:
            return f"{prefix} {who} arrived from {event.data['from']}"
        return f"{prefix} {who} left for {event.data['to']}"
    if event.type in ITEM_VERBS:
        return f"{prefix} {describe_item_event(event, world, viewer_id, who)}"
    return f"{prefix} {who} did {event.type}"


def describe_item_event(event: Event, world: World, viewer_id: str, who: str) -> str:
    """e.g. 'Wren (player) showed you the bloody knife (a kitchen knife ...)'."""
    verb = ITEM_VERBS[event.type]
    name = event.data["item_name"]
    to = event.data.get("to")
    if event.type in ("take", "drop"):
        return f"{who} {verb} the {name}"
    # Give and show carry the description, so the evidence itself is remembered.
    detail = f"the {name} ({event.data['item_description']})"
    if to is None:
        return f"{who} {verb} everyone here {detail}"  # a show with no one singled out
    target = "you" if to == viewer_id else name_of(world, to)
    return f"{who} {verb} {target} {detail}"


def importance_of(event: Event, viewer_id: str) -> int:
    """Importance by rule, no model call. 1 = trivial, 10 = life changing."""
    if event.type == "talk":
        return 6 if event.data["to"] == viewer_id else 4  # addressed to me vs overheard
    if event.type == "move":
        return 2
    # Handing over or showing an item is big news, most of all for the person it is for.
    if event.type in ("give", "show"):
        return 8 if event.data.get("to") == viewer_id else 7
    # Picking up or dropping something is noticeable but not dramatic.
    if event.type in ("take", "drop"):
        return 5
    # The murder setup will add higher-importance kinds (a body, an accusation) later.
    return 3
