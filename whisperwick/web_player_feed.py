"""Feed and live turn labels. Called only by the run thread, with the player lock."""

from whisperwick import player_terminal, story, web_scene, web_silence
from whisperwick.player import PLAYER_ID
from whisperwick.world import World


class WebPlayerFeed:
    def _catch_up(self, world: World) -> None:
        """Add feed lines for log events not looked at yet. Safe to call at any time:
        it goes by position in the log, so no event is ever added twice. Lock held."""
        events = world.log.all()
        fresh, self.seen = events[self.seen :], len(events)
        for event in fresh:
            lines = player_terminal.player_lines(world, [event], claims=False)  # words only
            self.feed += lines
            # What the 3D view animates: speech bubbles, hand-overs and walks. Display only.
            if lines and event.type == "talk":
                self.speech[event.actor] = lines[-1]
            if lines and event.type in {"give", "take", "show"}:
                self.interactions[event.actor] = {"id": event.actor, "sequence": len(self.feed)}
            if lines and event.type == "move":
                self.motions[event.actor] = web_scene.walk(world, event, len(self.feed))
            self.lines_by[event.actor] = self.lines_by.get(event.actor, 0) + len(lines)
            if lines and event.actor != PLAYER_ID:
                self.others += 1  # something Wren can see that someone else did or said

    def _show_look(self, world: World, seen: dict) -> None:
        """Wren's own look. A look is not a logged event, so without this line the feed
        showed nothing and the button seemed broken (playtest, 3D page). Lock held."""
        def names(ids, table):
            return ", ".join(table[i].name for i in ids)

        held = set(seen.get("held", []))
        people = ", ".join(world.npcs[n].name + (" (held)" if n in held else "")
                           for n in seen["people"])
        parts = [f"People: {people or 'nobody'}."]
        if seen["bodies"]:
            parts.append(f"Bodies: {names(seen['bodies'], world.npcs)}.")
        parts.append(f"On the ground: {names(seen['items'], world.items) or 'nothing'}.")
        parts.append(f"Exits: {names(seen['exits'], world.locations)}.")
        place = world.locations[seen["location"]].name
        self.feed.append(f"{story.hhmm(world.clock.tick)}  {place}: You look around. "
                         + " ".join(parts))

    def _close_turn(self, world: World) -> None:
        """Show a quiet reply after the villager's real turn has finished. Lock held."""
        if self.turn_of is None:
            return
        npc_id, errors, lines, tick = self.turn_of
        self.turn_of, self.waiting_on = None, None
        if self.lines_by.get(npc_id, 0) > lines:
            return  # Its real action is already visible.
        if world.npcs[npc_id].location == world.npcs[PLAYER_ID].location:
            errored = self.stats.get("errors", 0) > errors
            self.feed.append(web_silence.silence_line(world, npc_id, errored, tick))
            self.others += 1  # A quiet reply also gives Wren her turn back.
            self.lines_by[npc_id] = lines + 1


    def on_event(self, world: World, event) -> None:
        """Run-loop hook: a villager event was just applied. Show it now if Wren may see it."""
        with self.cv:
            self._catch_up(world)  # the event is already in the log; same filter as always

    def on_turn(self, world: World, npc_id: str | None) -> None:
        """Run-loop hook: a model call starts (npc_id None = the day's thinking phase).

        The label names a villager only when that villager is where Wren is, so the
        page never shows who is where outside Wren's view.
        """
        with self.cv:
            self._catch_up(world)  # also shows Wren's own action right away
            self._close_turn(world)
            if npc_id is not None and npc_id == self.waiting_on:
                # The tick is kept: the turn is closed later, often after the clock has moved on.
                self.turn_of = (npc_id, self.stats.get("errors", 0), self.lines_by.get(npc_id, 0),
                                world.clock.tick)
            if npc_id is None:
                self.busy = "The villagers are thinking about the day..."
            elif world.npcs[npc_id].location == world.npcs[PLAYER_ID].location:
                self.busy = f"{world.npcs[npc_id].name} is thinking..."
            else:
                self.busy = "Someone elsewhere is acting..."

