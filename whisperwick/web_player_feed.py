"""Feed and live turn labels. Called only by the run thread, with the player lock."""

from whisperwick import narrator, player_terminal, story, web_scene, web_silence
from whisperwick.actions import Intent, do_look
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
                draft = self.talk_drafts.pop(event.actor, None)
                self.speech_stream.pop(event.actor, None)
                if draft and draft["message"].strip() == event.data.get("message"):
                    self.speech_stream[event.actor] = draft["sequence"]
                if event.data.get("to") == PLAYER_ID:
                    self.reply_to = {"id": event.actor, "sequence": len(self.feed)}
            if lines and event.type in {"give", "take", "show", "use", "gesture"}:
                self.interactions[event.actor] = {"id": event.actor, "sequence": len(self.feed)}
            if event.type == "move" and event.actor == PLAYER_ID:
                self.reply_to = None  # A new room starts a new conversation.
            if lines and event.type == "move":
                self.motions[event.actor] = web_scene.walk(world, event, len(self.feed))
            for step in event.data.get("steps", []):
                if PLAYER_ID not in step["witnesses"]:
                    continue
                if step["effect"] == "move_self_exit":
                    move = event.model_copy(update={"data": step})
                    self.motions[event.actor] = web_scene.walk(world, move, len(self.feed))
                else:
                    self.interactions[event.actor] = {"id": event.actor,
                                                      "sequence": len(self.feed)}
            self.lines_by[event.actor] = self.lines_by.get(event.actor, 0) + len(lines)
            if lines and event.actor != PLAYER_ID:
                self.others += 1  # something Wren can see that someone else did or said

    def _show_look(self, world: World, seen: dict) -> None:
        """Wren's own look. A look is not a logged event, so without this line the feed
        showed nothing and the button seemed broken (playtest, 3D page). Lock held."""
        line = f"{story.hhmm(world.clock.tick)}  " + narrator.scene(world, seen, self.sc.seed)
        if self.feed and self.feed[-1] == line:
            # Same minute, same place, nothing new: a word-for-word repeat read as a
            # duplicate in play (2026-10-21), so say plainly that nothing changed.
            line = f"{story.hhmm(world.clock.tick)}  You look around again. Nothing has changed."
        self.scene_lines.add(len(self.feed))
        self.feed.append(line)

    def _show_arrival(self, world: World) -> None:
        """Include the starting place. Repeated refreshes must not repeat the scene."""
        here = world.npcs[PLAYER_ID].location
        if here != self.scene_place:
            self.scene_place = here
            seen = do_look(world, Intent(actor=PLAYER_ID, action="look")).observation
            self._show_look(world, seen)

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


    def on_live_talk(self, world: World, npc_id: str, message: str | None) -> None:
        """Only the run thread reads world locations. Server threads see plain data."""
        with self.cv:
            npc = world.npcs[npc_id]
            if (message is not None and not self.finished and not self.stopped
                    and npc.location == world.npcs[PLAYER_ID].location):
                if npc_id not in self.live_talk:
                    self.live_sequence += 1
                line = {"name": npc.name, "message": message,
                        "sequence": self.live_talk.get(npc_id, {}).get(
                            "sequence", self.live_sequence)}
                self.live_talk[npc_id] = line
                self.talk_drafts[npc_id] = line
            else:
                self.live_talk.pop(npc_id, None)

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
            self.talk_drafts.clear()  # A rejected preview cannot match a later turn.
            self._refresh(world)  # also shows Wren's own action right away
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

