"""Thinking: records, citation checks, hunches, model errors, and the run schedule."""

import json

from helpers import SCENARIO, fresh_world

from whisperwick import thinking
from whisperwick.belief_log import BeliefLog
from whisperwick.clock import MINUTES_PER_DAY, Clock
from whisperwick.llm_client import FakeClient
from whisperwick.llm_sim import THINK_EVERY, run_llm
from whisperwick.memory import MemoryStream
from whisperwick.scenario import load_scenario

EVIDENCE = "I saw Victor hurrying away from the Town Hall."


def bob_stream():
    """m0 is evidence, m1 is an event memory (event 7), m2 is a look."""
    s = MemoryStream()
    s.add(480, EVIDENCE, 9, "evidence")
    s.add(500, "Victor said: I was asleep.", 6, event_id=7)
    s.add(510, "You looked around and saw nobody", 1)
    return s


def good(**kw):
    base = {
        "thoughts": "Victor lied to me.",
        "suspect": "npc_victor",
        "sureness": "fairly sure",
        "because": ["m0", "m1"],
        "trust": [{"person": "npc_hal", "level": "high", "why": "honest guard"}],
    }
    return {**base, **kw}


def think(reply, stream=None, stats=None, log=None, personality="Blunt."):
    stream = stream if stream is not None else bob_stream()
    log = log if log is not None else BeliefLog()
    client = FakeClient([reply])
    got = thinking.think(stream, "npc_bob", fresh_world(), client, 600, personality, log, stats)
    return got, stream, log, client


def test_think_builds_a_record_and_a_reflection_memory():
    stats = {}
    rec, stream, log, _ = think(good(), stats=stats)
    assert rec == log.latest("npc_bob")
    assert (rec["tick"], rec["npc"], rec["suspect"], rec["sureness"]) == (
        600, "npc_bob", "npc_victor", "fairly sure",
    )  # fmt: skip
    assert rec["hunch"] is False and rec["after_event"] == 0  # no events in a fresh world
    # Each citation carries the event id behind the memory (None for evidence).
    assert rec["because"] == [
        {"memory_id": "m0", "event_id": None, "text": EVIDENCE},
        {"memory_id": "m1", "event_id": 7, "text": "Victor said: I was asleep."},
    ]
    assert rec["trust"] == [{"person": "npc_hal", "level": "high", "why": "honest guard"}]
    last = stream.memories[-1]
    assert (last.kind, last.importance, last.tick, last.text) == (
        "reflection", 8, 600, "Victor lied to me.",
    )  # fmt: skip
    assert "hunches" not in stats and "bad_citations" not in stats


def test_after_event_is_the_highest_event_id_in_the_log():
    w = fresh_world()
    w.act({"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": "hi"})
    last = w.act(
        {"actor": "npc_bob", "action": "talk", "target": "npc_victor", "message": "again"}
    ).event
    log = BeliefLog()
    thinking.think(bob_stream(), "npc_bob", w, FakeClient([good()]), 600, None, log)
    assert log.latest("npc_bob")["after_event"] == last.id == 2


def test_prompt_shows_character_ids_and_the_previous_belief():
    log = BeliefLog()
    think(good(), log=log)
    _, _, _, client = think(good(thoughts="Still Victor."), log=log)
    text = client.calls[0]["messages"][0]["content"]
    assert "Your character: Blunt." in text
    assert "[m0] I saw Victor hurrying" in text and "[m2] You looked around" in text
    assert (
        "What you think right now: you suspect Victor (npc_victor), fairly sure. Victor lied"
        in text
    )
    # Nothing in the prompt tells the villager there was a murder: only its memories can.
    assert "killed" not in text.split("Your memories")[0]
    assert "killed the mayor" not in client.calls[0]["messages"][1]["content"]


def test_of_what_is_kept_only_with_a_suspect():
    log = BeliefLog()
    rec, *_ = think(good(of_what="  killing the   mayor "), log=log)
    assert log.latest("npc_bob")["of_what"] == "killing the mayor"
    think(good(suspect=None, of_what="something"), log=log)
    assert log.latest("npc_bob")["of_what"] is None


def test_schema_only_allows_shown_memories_and_real_people():
    _, _, _, client = think(good())
    props = client.calls[0]["schema"]["properties"]
    assert props["because"]["maxItems"] == 5 and props["because"]["items"]["enum"] == [
        "m0",
        "m1",
        "m2",
    ]
    assert props["thoughts"]["maxLength"] == 400
    assert props["sureness"]["enum"] == ["unsure", "fairly sure", "certain"]
    assert "npc_bob" in props["suspect"]["enum"] and None in props["suspect"]["enum"]
    assert "npc_mayor" not in props["suspect"]["enum"]
    person = props["trust"]["items"]["properties"]
    assert props["trust"]["maxItems"] == 6 and person["why"]["maxLength"] == 150
    assert "npc_bob" not in person["person"]["enum"] and "npc_mayor" not in person["person"]["enum"]
    assert person["level"]["enum"] == ["low", "medium", "high"]


def test_reflections_are_not_shown_and_only_the_last_30_others_are():
    s = MemoryStream()
    s.add(0, "evidence line", 9, "evidence")
    for i in range(40):
        s.add(i, f"saw thing {i}", 1)
    s.add(50, "my earlier thought", 8, "reflection")
    shown = thinking.shown_memories(s)
    texts = [m.text for m in shown.values()]
    assert texts[0] == "evidence line" and "my earlier thought" not in texts
    assert len(shown) == 31 and "saw thing 9" not in texts and "saw thing 10" in texts
    assert "m1" not in shown and "m40" in shown  # ids are the stream index


def test_fake_citations_are_dropped_and_counted():
    stats = {}
    rec, *_ = think(good(because=["m0", "m99", "m1", "m0"]), stats=stats)
    assert [b["memory_id"] for b in rec["because"]] == ["m0", "m1"]  # m0 only once
    assert stats["bad_citations"] == 1 and rec["hunch"] is False


def test_unknown_people_in_trust_are_dropped():
    bad = [
        {"person": "npc_nobody", "level": "high", "why": "x"},
        {"person": "npc_bob", "level": "high", "why": "me"},  # not myself
        {"person": "npc_mayor", "level": "low", "why": "dead"},
        {"person": "npc_hal", "level": "high", "why": "ok " + "w" * 300},
        {"person": "npc_hal", "level": "low", "why": "twice"},
    ]
    rec, *_ = think(good(trust=bad))
    assert [t["person"] for t in rec["trust"]] == ["npc_hal"]
    assert len(rec["trust"][0]["why"]) == 150


def test_a_suspect_with_no_valid_citation_is_a_hunch():
    stats = {}
    rec, *_ = think(good(because=["m99"]), stats=stats)
    assert rec["suspect"] == "npc_victor" and rec["because"] == [] and rec["hunch"] is True
    assert stats["hunches"] == 1 and stats["bad_citations"] == 1
    # No suspect and no citation is simply "I don't know", not a hunch.
    rec, *_ = think(good(suspect=None, because=[]), stats=stats)
    assert rec["hunch"] is False and stats["hunches"] == 1


def test_the_killer_may_name_itself():
    s = MemoryStream()
    s.add(0, "I killed the mayor.", 9, "evidence")
    log = BeliefLog()
    client = FakeClient([good(suspect="npc_victor", because=["m0"])])
    got = thinking.think(s, "npc_victor", fresh_world(), client, 600, None, log)
    assert got["suspect"] == "npc_victor"


def test_thoughts_are_flattened_and_trimmed():
    rec, stream, *_ = think(good(thoughts="line one\nline two " + "x" * 600))
    assert "\n" not in rec["thoughts"] and len(rec["thoughts"]) == 400
    assert stream.memories[-1].text == rec["thoughts"]


def test_model_errors_return_none_count_and_store_nothing():
    stats = {}
    for reply in [
        {"oops": 1},  # missing keys
        good(suspect="npc_nobody"),
        good(sureness="very"),
        good(because="m0"),
        good(trust=[{"person": "npc_hal"}]),
    ]:
        rec, stream, log, _ = think(reply, stats=stats)
        assert rec is None and len(stream.memories) == 3 and log.records == []
    assert stats["thought_errors"] == 5
    # The client itself failing (nothing queued) is counted the same way.
    got = thinking.think(bob_stream(), "npc_bob", fresh_world(), FakeClient([]), 1, None,
                         BeliefLog(), stats)  # fmt: skip
    assert got is None and stats["thought_errors"] == 6


def test_an_empty_stream_makes_no_call():
    client = FakeClient([])
    got = thinking.think(MemoryStream(), "npc_bob", fresh_world(), client, 1, None, BeliefLog())
    assert got is None and client.calls == []


# ---- the schedule ----


class TimedClient:
    """Looks every turn. Notes the clock and the villager at every thinking call."""

    def __init__(self, world):
        self.world, self.thoughts = world, []

    def chat(self, messages, schema):
        if "thoughts" in schema["properties"]:
            who = messages[0]["content"].split("(")[1].split(")")[0]
            self.thoughts.append((self.world.clock.tick, who))
            return {"thoughts": "quiet", "suspect": None, "sureness": "unsure",
                    "because": [], "trust": []}  # fmt: skip
        return {"action": "look", "target": None, "item": None, "message": None}


def hours_of(client):
    return sorted({Clock(t).label().split(" ", 2)[2] for t, _ in client.thoughts})


def test_villagers_think_every_four_awake_hours_and_at_bedtime():
    assert THINK_EVERY == 240
    w = fresh_world()
    client, stats, log = TimedClient(w), {}, BeliefLog()
    run_llm(w, client, 14 * 60, stats=stats, belief_log=log)  # 08:00 to 22:00
    assert hours_of(client) == ["12:00", "16:00", "20:00", "22:00"]
    assert stats["thoughts"] == len(log.records) == 4 * 5


def test_nobody_thinks_while_asleep_and_the_player_never_thinks():
    w = fresh_world()
    client, log = TimedClient(w), BeliefLog()
    run_llm(w, client, MINUTES_PER_DAY, belief_log=log)  # 08:00 to 08:00
    # 22:00 is bedtime; 02:00 and 06:00-ish multiples of 4h fall in the night and are skipped.
    assert hours_of(client) == ["08:00", "12:00", "16:00", "20:00", "22:00"]
    assert {who for _, who in client.thoughts} == {
        "npc_alice", "npc_bob", "npc_hal", "npc_sarah", "npc_victor",
    }  # fmt: skip
    assert not any(r["npc"] in ("player", "npc_mayor") for r in log.records)


def test_a_run_saves_thoughts_to_the_jsonl_file(tmp_path):
    w = fresh_world()
    path = tmp_path / "r.beliefs.jsonl"
    run_llm(w, TimedClient(w), 5 * 60, belief_log=BeliefLog(path))
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    assert len(lines) == 5 and {x["tick"] for x in lines} == {12 * 60}


def test_run_with_evidence_cites_real_memories():
    sc = load_scenario(SCENARIO)
    w = fresh_world()

    class Citer(TimedClient):
        def chat(self, messages, schema):
            out = super().chat(messages, schema)
            if "thoughts" in schema["properties"]:
                out["suspect"], out["because"] = (
                    "npc_victor",
                    schema["properties"]["because"]["items"]["enum"][:1],
                )
            return out

    log, stats = BeliefLog(), {}
    run_llm(w, Citer(w), 4 * 60, evidence=sc.evidence, belief_log=log, stats=stats)
    assert stats.get("hunches", 0) == 0 and stats.get("bad_citations", 0) == 0
    # Evidence comes first in every stream, so m0 is the starting evidence for everyone.
    assert all(r["because"][0]["memory_id"] == "m0" for r in log.records)
