"""Terminal player: shows what Wren sees, reads one command, repeats."""

from collections.abc import Callable

from whisperwick import story
from whisperwick.actions import ActionResult, Intent
from whisperwick.player import PLAYER_ID, PlayerSource
from whisperwick.player_commands import HELP, parse_command
from whisperwick.world import World


def label(world: World, thing_id: str) -> str:
    """'Bob (npc_bob)': the name to read and the id to type."""
    thing = world.npcs.get(thing_id) or world.locations.get(thing_id) or world.items.get(thing_id)
    return f"{thing.name} ({thing_id})" if thing else thing_id


def view_lines(world: World) -> list[str]:
    """What the player sees right now. Read straight from the world, nothing is changed."""
    here = world.npcs[PLAYER_ID].location

    def names(ids: list[str]) -> str:
        return ", ".join(label(world, i) for i in ids) or "nobody/nothing"

    people = [n for n in world.npcs_at(here) if n != PLAYER_ID]
    lines = [
        f"--- {world.clock.label()} ---",
        f"You are at {label(world, here)}.",
        f"People here: {names(people)}",
        f"Exits: {names(sorted(world.locations[here].links))}",
    ]
    if bodies := world.bodies_at(here):
        lines.append(f"Bodies: {names(bodies)}")
    lines.append(f"On the ground: {names(world.items_at(here))}")
    lines.append(f"You carry: {names(world.items_held(PLAYER_ID))}")
    return lines


class TerminalPlayer(PlayerSource):
    def __init__(
        self,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ):
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.wait_left = 0  # quiet minutes still to pass before the next prompt
        self.seen = 0  # how many log events the player has already been shown

    def new_events(self, world: World) -> list[str]:
        """Events since the last prompt that the player did, saw, or was spoken to in."""
        events = world.log.all()
        fresh, self.seen = events[self.seen :], len(events)
        names = {i: x.name for d in (world.npcs, world.locations) for i, x in d.items()}
        mine = [
            e for e in fresh
            if PLAYER_ID in (e.actor, e.data.get("to"), *e.witnesses)
        ]  # fmt: skip
        return [line for e in mine if (line := story.format_event(e, names))]

    def turn(self, world: World) -> list[Intent] | None:
        if self.wait_left > 0:
            self.wait_left -= 1
            return []
        for line in [*view_lines(world), *self.new_events(world)]:
            self.output_fn(line)
        while True:
            try:
                parsed = parse_command(self.input_fn("> "))
            except EOFError:
                return None  # input ended, same as quit
            if parsed is None:
                self.output_fn("I did not understand that.")
                self.output_fn(HELP)
                continue
            kind, data = parsed
            if kind == "quit":
                return None
            if kind == "help":
                self.output_fn(HELP)
            elif kind == "look":
                # The view above is the look, so it costs no game time.
                for line in view_lines(world):
                    self.output_fn(line)
            elif kind == "wait":
                self.wait_left = data - 1  # this minute is the first one
                return []
            else:
                return [data]

    def report(self, intent: Intent, result: ActionResult) -> None:
        if not result.ok:
            self.output_fn(f"You cannot do that: {result.reason}")
