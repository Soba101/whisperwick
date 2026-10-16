"""Agent-side pair history and queued intents. The engine still resolves each line."""

from whisperwick.actions import Intent
from whisperwick.exchange_prompt import build_messages, build_schema, parse_lines
from whisperwick.llm_client import LLMError
from whisperwick.player import PLAYER_ID


class Exchanges:
    """Keep planned speech separate from the events the engine accepts."""

    def __init__(self, world, scheduler, memories, stats, log, personalities, history, on_event):
        """Share run services so queued speech follows the ordinary turn rules."""
        self.world, self.scheduler, self.memories = world, scheduler, memories
        self.stats, self.log, self.personalities = stats, log, personalities
        self.history, self.on_event = history, on_event
        # Ordinary turns must establish mutual talk before a shared call is allowed.
        self.own = set()
        # The latest speaker identifies who an answer would address.
        self.last_talk = {}
        # Keep future lines as intents because circumstances may change before delivery.
        self.pending = []
        # A queued line uses both speakers' conversation turn for this minute.
        self.blocked = set()
        # Initialize counters even when the run never starts an exchange.
        for key in ("exchanges", "exchange_lines", "exchange_failed", "exchange_dropped",
                    "exchange_cut"):
            stats.setdefault(key, 0)

    def problem(self, a, b):
        """Recheck whether the pair can still speak before using planned lines."""
        # Queued speech follows the same quiet hours as ordinary decisions.
        if self.scheduler.asleep(self.world.clock.tick):
            return "night"
        # Either speaker's condition can make the remaining conversation impossible.
        for npc in (a, b):
            person = self.world.npcs[npc]
            if not person.alive:
                return "dead"
            if person.held_by is not None:
                return "held"
        # Lines planned together cannot continue after the speakers separate.
        if self.world.npcs[a].location != self.world.npcs[b].location:
            return "apart"
        return None

    def finish(self, entry, reason=None):
        """Write one final record, so disk and in-memory logs agree."""
        record = entry["record"]
        record["dropped"] = reason
        self.log.add(record)
        self.pending.remove(entry)
        if reason:
            self.stats["exchange_dropped"] += 1
            # A canceled queue must no longer suppress ordinary decisions.
            self.blocked.difference_update((record["npc"], record["with"]))

    def observe(self, event, own=False):
        """External talk can cut in, even when it comes from the player."""
        if event.type == "talk":
            to = event.data["to"]
            self.last_talk[to] = event.actor
            # Queued lines do not count toward earning another shared call.
            if own:
                self.own.add((event.actor, to))
            # Finish may remove entries, so iterate over a snapshot.
            for entry in list(self.pending):
                r = entry["record"]
                pair = {r["npc"], r["with"]}
                if to in pair and event.actor not in pair:
                    self.finish(entry, "interrupted")
        # Moves and custody can invalidate a pair before its next queued minute.
        for entry in list(self.pending):
            r = entry["record"]
            if reason := self.problem(r["npc"], r["with"]):
                self.finish(entry, reason)

    def start_minute(self):
        """Deliver queued speech before ordinary decisions can use this minute."""
        # Last minute's speakers may act again unless another queued line blocks them.
        self.blocked.clear()
        for entry in list(self.pending):
            # An earlier delivery may have canceled another pending exchange.
            if entry in self.pending:
                self.deliver(entry)

    def eligible(self, a, reason):
        """Require an ordinary mutual conversation before sharing a call."""
        b = self.last_talk.get(a)
        # Only a scheduled villager's answer can start an exchange.
        if (reason != "answer" or b == PLAYER_ID or b == a
                or b not in self.scheduler.last or self.problem(a, b)):
            return None
        # A speaker cannot belong to two exchanges or take two turns this minute.
        busy = self.blocked | {n for e in self.pending
                               for n in (e["record"]["npc"], e["record"]["with"])}
        if a in busy or b in busy or not {(a, b), (b, a)} <= self.own:
            return None
        return b

    def begin(self, a, b, client):
        """Request planned lines and let the engine try the first one now."""
        # Count the attempted call even when its reply cannot be used.
        self.stats["turn_reasons"]["exchange"] += 1
        self.stats["calls"] = self.stats.get("calls", 0) + 1
        # One record links the whole reply to the individual events it produces.
        record = dict(kind="exchange", tick=self.world.clock.tick, npc=a,
                      with_=b, lines=0, logged=0, event_ids=[], dropped=None, cut=None)
        record["with"] = record.pop("with_")
        try:
            lines, record["cut"] = parse_lines(client.chat(
                build_messages(self.world, a, b, self.personalities), build_schema(a, b)), a, b)
            # Count cuts even when no usable first line remains for the engine.
            if record["cut"]:
                self.stats["exchange_cut"] += 1
            if not lines:
                raise ValueError("exchange has no valid lines")
        except (LLMError, ValueError, TypeError) as error:
            # Preserve failure details so the run can report errors and fall back.
            self.stats["exchange_failed"] += 1
            self.stats["errors"] = self.stats.get("errors", 0) + 1
            self.stats["errors_in_a_row"] = self.stats.get("errors_in_a_row", 0) + 1
            self.stats["last_error"] = str(error)
            reasons = self.stats.setdefault("error_reasons", {})
            reason = getattr(error, "reason", "bad reply")
            reasons[reason] = reasons.get(reason, 0) + 1
            record["dropped"] = "bad reply"
            self.log.add(record)
            return False
        # A usable reply breaks the failure streak even before engine validation.
        self.stats["errors_in_a_row"] = 0
        self.stats["exchanges"] += 1
        record["lines"] = len(lines)
        # Only validated slots reach the engine with their fixed alternating speakers.
        intents = [Intent(actor=a if i % 2 == 0 else b, action="talk",
                          target=b if i % 2 == 0 else a, message=line)
                   for i, line in enumerate(lines)]
        entry = {"record": record, "intents": intents}
        self.pending.append(entry)
        # Both must speak in their own turns again before another exchange.
        self.own.difference_update(((a, b), (b, a)))
        return self.deliver(entry)

    def deliver(self, entry):
        """Resolve one planned line against the world as it stands now."""
        r = entry["record"]
        # Conditions at generation time do not guarantee the pair can still talk.
        if reason := self.problem(r["npc"], r["with"]):
            self.finish(entry, reason)
            return False
        intent = entry["intents"].pop(0)
        # Only the engine may turn planned speech into a world event.
        result = self.world.act(intent)
        if not result.ok:
            # Later lines may rely on rejected speech, so discard the rest together.
            self.stats["rejected"] = self.stats.get("rejected", 0) + 1
            self.finish(entry, "rejected: " + result.reason)
            return False
        # Block through the last line's minute too. Its reply belongs to the next minute.
        self.blocked.update((r["npc"], r["with"]))
        # Ordinary scheduling and repeat checks must see queued speech as an action.
        self.scheduler.acted(intent.actor, self.world.clock.tick)
        self.history.record(self.world.clock.tick, intent)
        event = result.event
        # Remember and announce accepted speech before any later turn reads it.
        self.memories.observe(event, self.world)
        self.scheduler.notice(event)
        # Track accepted events separately from the number of proposed lines.
        r["logged"] += 1
        r["event_ids"].append(event.id)
        self.stats["exchange_lines"] += 1
        # Accepted speech can change which other queued conversations remain valid.
        self.observe(event)
        if self.on_event:
            self.on_event(self.world, event)
        # Observation may already have finished this entry while handling the event.
        if not entry["intents"] and entry in self.pending:
            self.finish(entry)
        return True

    def close(self):
        """Finalize pending records so a stopped run leaves no invisible queue."""
        # A short run can stop between lines; make the unfinished exchange inspectable.
        for entry in list(self.pending):
            self.finish(entry, "run ended")
