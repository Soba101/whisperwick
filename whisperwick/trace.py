"""Trace: who believes SUBJECT did it, and where each belief came from. Pure, no model.

Inputs are the event log (events by id) and the belief log. Nothing is written.
The code never decides what anyone believes. It only follows the receipts:
a villager's belief cites memories, a memory points at an event, a talk event
points at a speaker, and the speaker's own belief (just before that talk) cites more.
The chain ends at something seen first-hand, someone talking about themselves,
or "no source: made up" (the player's lie, or a guess).
"""

import re
from dataclasses import dataclass

from whisperwick.belief_log import BeliefLog
from whisperwick.claims import claim_words, kind_of
from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.player import PLAYER_ID

MAX_DEPTH = 6  # how many people back we follow a rumour before giving up
SURENESS_ORDER = {"certain": 0, "fairly sure": 1, "unsure": 2}
LOOK_WORDS = "you looked around"  # a look memory (no event) says this; starting evidence does not


def node(kind: str, text: str, event_id: int | None = None, then: list | None = None) -> dict:
    """One step in a chain. `then` holds the steps behind it (empty = the chain ends here)."""
    return {"kind": kind, "text": text, "event_id": event_id, "then": then or []}


@dataclass
class Tracer:
    """Everything a trace reads, bundled so the helpers stay short."""

    events: list[Event]
    log: BeliefLog
    subject: str
    names: dict[str, str]

    def name(self, thing_id: str) -> str:
        return self.names.get(thing_id, thing_id)

    def where(self, e: Event) -> str:
        return f"event {e.id}, {Clock(e.tick).label()}"

    def mentions_subject(self, e: Event) -> bool:
        """A talk that accuses the subject (claim) or just says their name."""
        claim = e.data.get("claim")
        if claim and claim["subject"] == self.subject and kind_of(claim) == "accuses":
            return True
        # Whole words only, so "Hal" does not match "shall".
        # Without a scenario to give names, "npc_hal" still matches the word "hal".
        words = {self.subject, self.name(self.subject), self.subject.removeprefix("npc_")}
        return any(re.search(rf"\b{re.escape(w)}\b", e.data["message"], re.I) for w in words)

    def heard_before(self, person: str, event: Event) -> Event | None:
        """The latest talk before this event that `person` heard and that was about the subject."""
        heard = [
            e for e in self.events
            if e.id < event.id and e.type == "talk" and person in e.witnesses
            and e.actor != person and self.mentions_subject(e)
        ]  # fmt: skip
        return heard[-1] if heard else None

    # ---- the chain -----------------------------------------------------------

    def explain_record(self, record: dict, depth: int, seen: frozenset) -> list[dict]:
        """Why this belief: one step per cited memory, or a hunch if it cited none."""
        if not record["because"]:
            return [node("hunch", "a hunch: no memory cited")]
        return [self.explain_cite(record["npc"], c, depth, seen) for c in record["because"]]

    def explain_cite(self, who: str, cite: dict, depth: int, seen: frozenset) -> dict:
        """Turn one cited memory into a step. Only another person's talk goes further back."""
        text, event = cite["text"], None
        if cite["event_id"] is not None:
            event = next((e for e in self.events if e.id == cite["event_id"]), None)
        if event is None:
            # No event behind it: either a look, or evidence the villager began with.
            if LOOK_WORDS in text:
                return node("saw", f"saw: {text}")
            return node("start", f"remembered from the start: {text}")
        if event.type == "talk" and event.actor == who:
            # Citing what it said itself is not seeing anything. Say so plainly; the chain ends.
            return node("own_words", f"its own words: {text}", event.id)
        if event.type != "talk":
            # Shown, given, taken or moved: first-hand, the chain ends here.
            return node("saw", f"saw: {text}", event.id)
        say = f'{self.name(event.actor)} said: "{event.data["message"]}"{self.claim_text(event)}'
        then = self.speaker_source(event.actor, event, depth + 1, seen)
        return node("said", f"{say} ({self.where(event)})", event.id, then)

    def claim_text(self, e: Event) -> str:
        claim = e.data.get("claim")
        if not claim:
            return ""
        text = f" [claim: {claim_words(claim, self.name(claim['subject']))}]"
        return text + (" (unverified tag)" if claim.get("unverified") else "")

    def speaker_source(self, p: str, event: Event, depth: int, seen: frozenset) -> list[dict]:
        """Where did P get what P said at `event`? Always returns at least one step."""
        key = (p, event.id)
        if key in seen:  # a hand-made or odd log could loop: say so and stop
            return [node("loop", "(already followed above)")]
        if depth > MAX_DEPTH:
            return [node("deep", "(stopped: too many steps back)")]
        seen = seen | {key}
        # 1. P itself suspected the subject just before, so follow what P relied on.
        record = self.log.before(p, event.id)
        if record and record["suspect"] == self.subject:
            return self.explain_record(record, depth, seen)
        # 2. P had been told about the subject by someone else earlier.
        heard = self.heard_before(p, event)
        if heard:
            line = f"{self.name(p)} had heard it from {self.name(heard.actor)}: "
            line += f'"{heard.data["message"]}" ({self.where(heard)})'
            then = self.speaker_source(heard.actor, heard, depth + 1, seen)
            return [node("heard", line, heard.id, then)]
        # 3. Nothing to follow back to.
        who = self.name(p)
        if p == self.subject:
            return [node("self", f"{who} was speaking about themselves")]
        if p == PLAYER_ID:
            return [node("made_up", f"{who} had no source: made up (the player)")]
        return [node("made_up", f"{who} had no source: made up (a guess or a lie)")]


def is_made_up(steps: list[dict]) -> bool:
    return steps[0]["kind"] == "made_up"


def believer_entry(t: Tracer, record: dict) -> dict:
    """A believer's own words plus the chain behind each cited memory."""
    npc = record["npc"]
    return {
        "npc": npc, "name": t.name(npc), "tick": record["tick"],
        "of_what": record.get("of_what"), "sureness": record["sureness"],
        "thoughts": record["thoughts"], "hunch": record.get("hunch", False),
        # Who it meant to accuse out loud (may differ from what it believes). Old records: None.
        "will_accuse": record.get("will_accuse"),
        "chain": t.explain_record(record, 0, frozenset()),
    }  # fmt: skip


def by_sureness(record: dict) -> tuple[int, str]:
    """Sort key: certain first, then fairly sure, then unsure; ties by villager id."""
    return SURENESS_ORDER.get(record["sureness"], 3), record["npc"]


def believers(log: BeliefLog, subject: str) -> tuple[list[dict], list[dict]]:
    """(suspect now, used to suspect): one record each, most sure first, then by id."""
    now, used_to = {}, {}
    for r in log.records:  # records are in order, so the last one wins
        if r["suspect"] == subject:
            used_to[r["npc"]] = r
    for npc in {r["npc"] for r in log.records}:
        latest = log.latest(npc)
        if latest["suspect"] == subject:
            now[npc] = used_to.pop(npc)  # its newest suspecting record is its latest one
    return sorted(now.values(), key=by_sureness), sorted(used_to.values(), key=by_sureness)


def trust_in_player(log: BeliefLog) -> dict[str, dict | None]:
    """Each villager's newest rating of the player (level + why), or None if never rated."""
    out: dict[str, dict | None] = {}
    for npc in sorted({r["npc"] for r in log.records}):
        out[npc] = None
        for r in log.records:
            for t in r["trust"]:
                if r["npc"] == npc and t["person"] == PLAYER_ID:
                    out[npc] = {"level": t["level"], "why": t["why"]}
    return out


def trace(events: list[Event], log: BeliefLog, subject: str, names: dict | None = None) -> dict:
    """The whole trace as plain data (this is what --json prints)."""
    t = Tracer(events, log, subject, names or {})
    now, used_to = believers(log, subject)
    return {
        "subject": subject,
        "believers": [believer_entry(t, r) for r in now],
        "used_to_suspect": [believer_entry(t, r) for r in used_to],
        "trust_in_player": trust_in_player(log),
    }


def own_claims(events: list[Event], log: BeliefLog, names: dict | None = None) -> list[Event]:
    """Accusations whose speaker had no source (by the same rules as the trace)."""
    out = []
    for e in events:
        claim = e.data.get("claim") if e.type == "talk" else None
        if claim and kind_of(claim) == "accuses":
            t = Tracer(events, log, claim["subject"], names or {})
            if is_made_up(t.speaker_source(e.actor, e, 0, frozenset())):
                out.append(e)
    return out
