"""Beliefs: who thinks who killed the mayor, and why. Agent side only.

A pure function of the event log plus the scenario. It is never part of World state
or state_hash, so it can be rebuilt from a run's .db file with no model.
Only structured claims (and clue items) change beliefs; free text never does.
"""

from dataclasses import asdict, dataclass

from whisperwick.clock import Clock
from whisperwick.events import Event
from whisperwick.player import PLAYER_ID
from whisperwick.trust import TRUST_DROP, TRUST_RISE, Trust, clamp

# The made-up numbers, in one place so they are easy to tune.
TELL_WEIGHT = 0.5  # how much a fully trusted teller can move my belief
SEE_WEIGHT = 0.3  # how much seeing a telling item moves it
FIRM = 0.5  # a first-hand belief this strong is firm enough to judge others by


@dataclass
class Source:
    """Where part of a belief came from."""

    type: str  # "saw" or "told"
    by: str | None  # the teller's id (told only)
    event_id: int | None  # None for starting beliefs
    tick: int
    note: str  # short text, e.g. "starting evidence"


class BeliefState:
    def __init__(self, trust: Trust, clues: dict[str, str], start_tick: int = 0):
        self.trust = trust
        self.clues = dict(clues)  # item id -> person it points to
        self.start_tick = start_tick
        # holder -> subject -> confidence / sources
        self.conf: dict[str, dict[str, float]] = {}
        self.sources: dict[str, dict[str, list[Source]]] = {}
        # (hearer, teller, kind, subject) already heard: hearing it again adds nothing.
        self.heard: set[tuple[str, str, str, str]] = set()

    @classmethod
    def from_scenario(cls, scenario) -> "BeliefState":
        start = Clock.at(scenario.start["day"], scenario.start["hour"]).tick
        state = cls(Trust.from_scenario(scenario), scenario.clues, start)
        # Rule 3: starting beliefs are first-hand ("saw"), with no event behind them.
        for holder in sorted(scenario.beliefs):
            for b in scenario.beliefs[holder]:
                state._set(holder, b.subject, b.confidence)
                state._add(holder, b.subject, Source("saw", None, None, start, b.note))
        return state

    # ---- small helpers ----
    def _set(self, holder: str, subject: str, c: float) -> None:
        self.conf.setdefault(holder, {})[subject] = clamp(c)

    def _add(self, holder: str, subject: str, source: Source) -> None:
        self.sources.setdefault(holder, {}).setdefault(subject, []).append(source)

    def confidence(self, holder: str, subject: str) -> float:
        return self.conf.get(holder, {}).get(subject, 0.0)

    def sources_before(self, holder: str, subject: str, event_id: int) -> list[Source]:
        """Sources the holder had before this event. Used to walk chains:
        a claim is 'own' (a guess or lie) if the teller had none here.

        Compared by event id, not tick: an NPC can hear a rumour and repeat it
        in the same game minute, and the event id still puts them in order.
        Starting beliefs have no event, so they always count as before."""
        return [
            s
            for s in self.sources.get(holder, {}).get(subject, [])
            if s.event_id is None or s.event_id < event_id
        ]

    def top(self, holder: str, exclude=()) -> tuple[str, float] | None:
        """The holder's strongest suspect, or None. Ties go to the lowest id."""
        best = None
        for subject in sorted(self.conf.get(holder, {})):
            c = self.conf[holder][subject]
            if subject not in exclude and c > 0 and (best is None or c > best[1]):
                best = (subject, c)
        return best

    def _firm_saw(self, holder: str) -> set[str]:
        """Subjects the holder saw first-hand and is firm about."""
        return {
            subject
            for subject, srcs in self.sources.get(holder, {}).items()
            if any(s.type == "saw" for s in srcs) and self.confidence(holder, subject) >= FIRM
        }

    # ---- the rules ----
    def apply(self, event: Event) -> None:
        if event.type == "talk" and event.data.get("claim"):
            self._hear_claim(event)
        elif event.type in ("show", "give") and event.data.get("item") in self.clues:
            self._see_clue(event)

    def _hear_claim(self, event: Event) -> None:
        """Rule 1: every hearer weighs the claim by how much they trust the speaker."""
        speaker, claim = event.actor, event.data["claim"]
        kind, x = claim["kind"], claim["subject"]
        # The player has no beliefs, and you do not hear yourself.
        for h in sorted(set(event.witnesses) - {speaker, PLAYER_ID}):
            # Rumours about myself: I know whether I did it, so nothing changes at all
            # (not even trust, or I would learn to trust whoever accused me correctly).
            if x == h:
                continue
            # The same claim from the same teller tells me nothing new. Without this,
            # a teller repeating one claim could push a hearer to near-certainty.
            key = (h, speaker, kind, x)
            if key in self.heard:
                continue
            self.heard.add(key)
            t = self.trust.get(h, speaker)  # trust BEFORE this event
            # Judge the claim against what I saw before it changed my mind.
            firm = self._firm_saw(h)
            c = self.confidence(h, x)
            c = c + t * TELL_WEIGHT * (1 - c) if kind == "killer" else c - c * t * TELL_WEIGHT
            self._set(h, x, c)
            note = "said killer" if kind == "killer" else "said innocent"
            self._add(h, x, Source("told", speaker, event.id, event.tick, note))
            # Trust update: does the claim clash with, or match, what I saw myself?
            if kind == "killer" and firm - {x}:
                self.trust.change(h, speaker, -TRUST_DROP)
            elif kind == "innocent" and x in firm:
                self.trust.change(h, speaker, -TRUST_DROP)
            elif kind == "killer" and x in firm:
                self.trust.change(h, speaker, TRUST_RISE)

    def _see_clue(self, event: Event) -> None:
        """Rule 2: seeing a telling item shown or given points me at its owner."""
        target = self.clues[event.data["item"]]
        seers = set(event.witnesses) | {event.data.get("to")}
        for h in sorted(s for s in seers if s and s not in (target, PLAYER_ID)):
            c = self.confidence(h, target)
            self._set(h, target, c + SEE_WEIGHT * (1 - c))
            verb = "shown" if event.type == "show" else "given"
            note = f"saw the {event.data.get('item_name', event.data['item'])} {verb}"
            self._add(h, target, Source("saw", None, event.id, event.tick, note))

    # ---- saving ----
    def to_dict(self) -> dict:
        """JSON-safe, sorted keys, for the sidecar file."""
        return {
            "start_tick": self.start_tick,
            "clues": dict(sorted(self.clues.items())),
            "trust": self.trust.to_dict(),
            "confidence": {h: dict(sorted(s.items())) for h, s in sorted(self.conf.items())},
            "sources": {
                h: {s: [asdict(x) for x in srcs] for s, srcs in sorted(subs.items())}
                for h, subs in sorted(self.sources.items())
            },
            "heard": [list(k) for k in sorted(self.heard)],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BeliefState":
        state = cls(Trust.from_dict(d["trust"]), d["clues"], d["start_tick"])
        state.conf = {h: dict(s) for h, s in d["confidence"].items()}
        state.sources = {
            h: {s: [Source(**x) for x in srcs] for s, srcs in subs.items()}
            for h, subs in d["sources"].items()
        }
        # Old files have no "heard" key.
        state.heard = {tuple(k) for k in d.get("heard", [])}
        return state


def replay(events: list[Event], scenario) -> BeliefState:
    """Rebuild beliefs from a log, applying events in id order."""
    state = BeliefState.from_scenario(scenario)
    for event in sorted(events, key=lambda e: e.id or 0):
        state.apply(event)
    return state
