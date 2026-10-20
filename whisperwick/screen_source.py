"""Saved replies rebuilt from run records, without deciding any world facts."""

import json
import re

from whisperwick import llm_run
from whisperwick.events import EventLog
from whisperwick.llm_client import LLMError


def json_lines(path):
    """Allow runs without optional records to replay alongside fuller runs."""
    # Empty logs may have no file because no record was ever appended.
    if not path.exists():
        return []
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def intent_reply(event=None):
    """Rebuild a reply so the engine resolves saved actions again."""
    reply = dict(action="look", target=None, item=None, message=None, accuses=None, defends=None)
    # A turn with no event is replayed as a harmless look.
    if event is None:
        return reply
    data = event.data
    reply.update(action=event.type, item=data.get("item"),
                 message=data.get("message", data.get("reason")))
    reply["target"] = data.get("target", data.get("to"))
    if event.type == "gesture":
        reply["text"] = data["text"]
    if "steps" in data:
        # Replay the proposal, never the engine's saved patches.
        reply["target"] = None
        if event.type == "make":
            reply.update(data["definition"])
            if "use" in data:
                reply["use"] = data["use"]
        else:
            reply.update(data["use"])
    if event.type == "talk" and data.get("claim"):
        # Saved claims use nested fields while replies use the flat prompt schema.
        claim = data["claim"]
        reply[claim["kind"]] = claim["subject"]
    return reply


class Source:
    """Index saved facts so replay can find replies by stable turn coordinates."""
    def __init__(self, db):
        """Keep saved replies separate from the live state used during replay."""
        self.db = str(db)
        self.sidecar = json.loads(llm_run.sidecar_path(db).read_text())
        self.events = EventLog.read(str(db))
        self.beliefs = json_lines(llm_run.beliefs_path(db))
        self.recalls = json_lines(llm_run.agent_log_path(db))
        # Tick and stable actor id identify turns independently of display names.
        self.actions = {(e.tick, e.actor): e for e in self.events}
        self.thoughts = {(b["tick"], b["npc"]): b for b in self.beliefs}
        self.used = set()

    def recall(self, tick, npc, when):
        """Consume each saved search once so follow-up calls cannot repeat it."""
        for i, r in enumerate(self.recalls):
            if (i not in self.used and r.get("kind") == "recall"
                    and (r["tick"], r["npc"], r["when"]) == (tick, npc, when)):
                self.used.add(i)
                return r["words"]
        return None

    @property
    def unused_recalls(self):
        """Expose leftover searches as a clue that the replay path changed."""
        return sum(r.get("kind") == "recall" and i not in self.used
                   for i, r in enumerate(self.recalls))


class ReplayClient:
    """Replace remote requests with saved replies while preserving normal turn flow."""
    def __init__(self, source, context, callback):
        """Keep saved replies separate from the live state used during replay."""
        self.source, self.context, self.callback = source, context, callback
        self.npc = None
        self.seen = set()

    def turn(self, world, npc):
        """Expose action state before the normal loop applies the saved reply."""
        self.npc = npc
        if npc is not None and self.callback:
            self.callback(self.context, npc, "act")

    def chat(self, messages, schema):
        """Feed saved replies through the same schemas and handlers as live turns."""
        c = self.context
        tick = c.world.clock.tick
        think = "thoughts" in schema["properties"]
        # The first line names the owner. Other ids later in the prompt are memories.
        first = messages[0]["content"].splitlines()[0]
        npc = re.search(r"\(([^()]+)\)", first)[1] if think else self.npc
        key = (tick, npc)
        # A recall follow-up belongs to the same thought and must not be sampled twice.
        if think and key not in self.seen:
            self.seen.add(key)
            if self.callback:
                self.callback(c, npc, "think")
        props = schema["properties"]
        # Only replay searches when the current schema allows a recall.
        offered = "recall" in props if think else "recall" in props["action"]["enum"]
        words = self.source.recall(tick, npc, "think" if think else "act") if offered else None
        if words:
            if think:
                return {"recall": words}
            return {**intent_reply(), "action": "recall", "message": words}
        if not think:
            return intent_reply(self.source.actions.get(key))
        saved = self.source.thoughts.get(key)
        if saved is None:
            raise LLMError("no saved thought")
        reply = {k: saved.get(k) for k in props}
        # Belief logs store citation details while replies expect only ids.
        reply["because"] = [b["memory_id"] for b in saved["because"]]
        if "recall" in props:
            reply["recall"] = None
        if "notebook_me" in props:
            book = saved["notebook"]
            old = c.notebooks.to_dict().get(npc, {"people": {}})
            # Snapshots must also clear notes that the saved thought removed.
            reply["notebook_me"] = book["me"] or ""
            reply["notebook_people"] = [
                {"person": n, "line": book["people"].get(n, "")}
                for n in sorted(old["people"].keys() | book["people"].keys())
                if old["people"].get(n) != book["people"].get(n)
            ]
        return reply
