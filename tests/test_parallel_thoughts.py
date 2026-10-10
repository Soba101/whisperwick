"""Thinking in parallel gives exactly the run that thinking one by one gives."""

import hashlib
import threading

from helpers import SCENARIO, fresh_world

from whisperwick.agent_log import AgentLog
from whisperwick.belief_log import BeliefLog
from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.llm_client import LLMError
from whisperwick.llm_sim import run_llm
from whisperwick.notebook import Notebooks
from whisperwick.scenario import build_world, load_scenario


def pick(seed: str, options: list):
    """A pure choice from a list: the same text always gives the same item."""
    return options[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(options)]


class HashClient:
    """Thread-safe: the reply depends only on (messages, schema). Never on call order."""

    def __init__(self):
        self.lock = threading.Lock()
        self.think_calls = 0

    def chat(self, messages, schema):
        key = repr(messages)
        props = schema["properties"]
        if "thoughts" in props:
            with self.lock:
                self.think_calls += 1
            return self.thought(key, props)
        return self.intent(key, props)

    def intent(self, key, props):
        action = pick(key, [a for a in props["action"]["enum"] if a in ("move", "talk", "look")])
        target = None
        if action == "move":
            target = pick(key, [t for t in props["target"]["enum"] if t])
        if action == "talk":
            target = pick(key, [t for t in props["target"]["enum"] if t])
        message = "Hello there." if action == "talk" else None
        return {"action": action, "target": target, "message": message}

    def thought(self, key, props):
        suspect = pick(key, [*props["suspect"]["enum"][:2], None])
        ids = props["because"]["items"]["enum"]
        because = [pick(key, ids)] if suspect and ids and len(key) % 2 else []
        return {
            "thoughts": "I think so " + key[-12:], "suspect": suspect, "of_what": "something",
            "sureness": "unsure", "will_accuse": None, "aim": None, "aim_status": None,
            "because": because, "trust": [],
        }  # fmt: skip


class RecallingClient(HashClient):
    """Some thoughts recall (decided by the prompt text), some acts recall, some write notes."""

    def intent(self, key, props):
        if "recall" in props["action"]["enum"] and len(key) % 3 == 0:
            return {"action": "recall", "target": None, "item": None, "message": "bob victor"}
        return super().intent(key, props)

    def thought(self, key, props):
        reply = super().thought(key, props)
        if "recall" in props and pick(key, [0, 1]):
            reply["recall"] = "victor market"
        elif "recall" in props:
            reply["recall"] = None
        if "notebook_me" in props:
            reply["notebook_me"] = pick(key, [None, "I keep to myself."])
            people = props["notebook_people"]["items"]["properties"]["person"]["enum"]
            reply["notebook_people"] = [{"person": pick(key, people), "line": "watch " + key[-5:]}]
        # A second-round reply may cite a recalled id: it is in the enum on that round only.
        return reply


def play_day(parallel, client=None, **kw):
    world = build_world(load_scenario(SCENARIO), ":memory:", seed=7)
    log, stats = BeliefLog(), {}
    client = client or HashClient()
    memories, stats = run_llm(
        world, client, MINUTES_PER_DAY, stats=stats, belief_log=log, parallel=parallel, **kw,
    )  # fmt: skip
    texts = {n: [m.text for m in s.memories] for n, s in memories.items()}
    return world, log.records, texts, stats


def test_parallel_day_equals_serial_day():
    a, b = play_day(1), play_day(4)
    assert a[3].get("thoughts", 0) > 0 and any(r["suspect"] for r in a[1])  # not trivial
    assert a[1] == b[1]  # belief records
    assert a[2] == b[2]  # every villager's memory texts
    assert a[0].log.all() == b[0].log.all()  # event log
    assert a[3] == b[3]  # stats
    assert a[0].state_hash() == b[0].state_hash()


class MeetingClient(HashClient):
    """Thinking calls wait for each other. They can only pass if they truly overlap."""

    def __init__(self, parties):
        super().__init__()
        self.barrier = threading.Barrier(parties, timeout=5)
        self.met = 0

    def chat(self, messages, schema):
        if "thoughts" in schema["properties"] and self.met == 0:
            self.barrier.wait()  # raises BrokenBarrierError on timeout
            with self.lock:
                self.met += 1
        return super().chat(messages, schema)


def test_thinking_calls_really_overlap():
    living = [n for n in fresh_world().npcs.values() if n.alive and n.id != "player"]
    parties = min(len(living), 3)
    client = MeetingClient(parties)
    world = fresh_world()
    run_llm(world, client, 4 * 60 + 1, parallel=parties, stats=(stats := {}))  # first thinking
    assert client.met >= parties and stats.get("thought_errors", 0) == 0


class FailsForBob(HashClient):
    def chat(self, messages, schema):
        # The first prompt line is "You are <name> (<id>), ...": it names only the thinker.
        first_line = messages[0]["content"].split("\n")[0]
        if "thoughts" in schema["properties"] and "(npc_bob)" in first_line:
            raise LLMError("model down")
        return super().chat(messages, schema)


def test_a_failing_thought_counts_like_serial_and_stops_nobody():
    a = play_day(1, FailsForBob())
    b = play_day(4, FailsForBob())
    # Bob thinks five times in a day (see test_llm_sim), and every one fails.
    assert a[3]["thought_errors"] == 5 and a[3]["last_thought_error"] == "model down"
    assert a[3] == b[3] and a[1] == b[1] and a[2] == b[2]
    assert a[3]["thoughts"] > 0  # the others still thought
    assert all(r["npc"] != "npc_bob" for r in b[1])


def test_parallel_with_recall_and_notebook_equals_serial():
    runs = []
    for parallel in (1, 4):
        nb, alog = Notebooks(), AgentLog()
        runs.append((play_day(parallel, RecallingClient(), notebooks=nb, agent_log=alog), nb, alog))
    (a, nba, loga), (b, nbb, logb) = runs
    assert a[3].get("recalls", 0) > 0 and any(r["recall"] for r in a[1])  # not trivial
    assert any(r["recalled"] for r in a[1]) and nba.to_dict()
    assert a[1] == b[1] and a[2] == b[2] and a[3] == b[3]
    assert a[0].log.all() == b[0].log.all() and a[0].state_hash() == b[0].state_hash()
    assert nba.to_dict() == nbb.to_dict() and loga.records == logb.records
    assert {r["when"] for r in loga.records} == {"act", "think"}
