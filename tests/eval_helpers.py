"""Small finished runs for the eval and judge tests. Fake clients only, no network."""

import json

from helpers import SCENARIO

from whisperwick import llm_run
from whisperwick.belief_log import BeliefLog
from whisperwick.events import Event
from whisperwick.llm_sim import run_llm
from whisperwick.scenario import build_world, load_scenario

TALK = {"action": "talk", "target": "npc_victor", "item": None,
        "message": "Victor, you know more than you say.", "accuses": "npc_victor",
        "defends": None}  # fmt: skip
LOOK = {"action": "look", "target": None, "item": None, "message": None,
        "accuses": None, "defends": None}  # fmt: skip


class BobAccuses:
    """Bob accuses Victor every turn. Everyone else looks. Thoughts are empty."""

    def __init__(self):
        self.said = 0  # the words change each time, or the repeat guard refuses them

    def chat(self, messages, schema):
        if "thoughts" in schema["properties"]:
            return {"thoughts": "quiet", "suspect": None, "sureness": "unsure",
                    "because": [], "trust": []}  # fmt: skip
        if "(npc_bob)" in messages[0]["content"]:
            self.said += 1
            return {**TALK, "message": f"{TALK['message']} ({self.said})"}
        return dict(LOOK)


def record(npc, suspect, because, thoughts="Victor hides something."):
    """A belief record shaped like the ones thinking.py writes."""
    return {"npc": npc, "tick": 600, "suspect": suspect, "of_what": "lying", "sureness": "unsure",
            "thoughts": thoughts, "because": [{"memory_id": "m1", "event_id": 1, "text": t}
                                              for t in because],
            "hunch": bool(suspect and not because), "aim_status": "new", "after_event": 1,
            "trust": [], "will_accuse": None, "aim": None}  # fmt: skip


def make_run(tmp_path, name="a", script="none", seed=1, memory=True, arrest="npc_bob",
             records=None) -> str:
    """Run two game hours, add an arrest and belief records, write the sidecar. Returns the db."""
    db = str(tmp_path / f"{name}.db")
    sc = load_scenario(SCENARIO)
    world = build_world(sc, db, seed=seed)
    log = BeliefLog(llm_run.beliefs_path(db))
    _, stats = run_llm(world, BobAccuses(), 120, belief_log=log, agent_memory=memory)
    if arrest:
        world.log.append(Event(tick=world.clock.tick, type="arrest", actor="npc_hal",
                               location="loc_town_hall", data={"target": arrest}))  # fmt: skip
    for r in records if records is not None else [
        record("npc_alice", "npc_victor", ["Victor came in with wet boots."]),
        record("npc_bob", "npc_hal", []),
    ]:
        log.add(r)
    data = llm_run.sidecar_data(SCENARIO, "m", 120, stats, sc.secrets, {}, script, log.path)
    data["seed"] = seed
    if memory:
        data["agent_memory"], data["recalls"] = True, {"act": 2, "think": 1}
    llm_run.write_sidecar(llm_run.sidecar_path(db), data)
    return db


def strip_week6(db: str) -> None:
    """Make the sidecar look like a week 5 run: no seed, no memory fields."""
    path = llm_run.sidecar_path(db)
    data = json.loads(path.read_text())
    for key in ("seed", "agent_memory", "recalls", "notebooks"):
        data.pop(key, None)
    path.write_text(json.dumps(data))
