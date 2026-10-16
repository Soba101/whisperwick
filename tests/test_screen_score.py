"""Candidate failures and successes must leave every part of replay state alone."""

from copy import deepcopy

import pytest
from test_llm_sim import LookClient
from test_screen_replay import source_fixture  # noqa: F401 (shared fixture)

from whisperwick.llm_client import FakeClient, LLMError
from whisperwick.screen_replay import check, difference, replay
from whisperwick.screen_results import run_picked, totals
from whisperwick.screen_score import score
from whisperwick.screen_turns import pick


class Illegal:
    def chat(self, messages, schema):
        return {"action": "move", "target": "loc_missing"}


class Broken:
    def chat(self, messages, schema):
        raise LLMError("invalid text", "bad JSON")


def snapshot(c):
    # Include memory ids and private logs, not only the engine state hash.
    streams = {n: s.memories for n, s in c.memories.items()}
    return deepcopy((c.world.state_hash(), c.world.log.all(), streams,
                     c.history.records, c.agent_log.records, c.notebooks.to_dict(),
                     c.belief_log.records))


@pytest.mark.parametrize("candidate", [Illegal(), Broken(), LookClient()])
def test_act_isolated_even_on_failure(saved_run, candidate):
    db = saved_run()
    records = []

    def visit(c, npc, kind):
        if records or kind != "act":
            return
        before = snapshot(c)
        records.append(score(c, npc, kind, candidate))
        assert snapshot(c) == before

    source, c = replay(db, visit)
    assert difference(source, c) is None
    c.world.log.db.close()
    r = records[0]
    if isinstance(candidate, Illegal):
        assert r["stats"]["rejected"] == r["stats"]["calls"] == 2
        assert r["fell_back_to_look"] and len(r["rejection_reasons"]) == 2
        assert totals(records)["rejected_share"] == 1
    elif isinstance(candidate, Broken):
        assert r["stats"]["errors"] == 1 and r["fell_back_to_look"]
        assert totals(records)["parse_rate"] == 0
        assert totals(records)["error_reasons"] == {"bad JSON": 1}
    else:
        assert r["first_try_accepted"] and not r["fell_back_to_look"]
    assert check(db)["ok"]


def test_accepted_action_and_recall_are_isolated(saved_run):
    db = saved_run()
    done = []

    def visit(c, npc, kind):
        if done or kind != "act":
            return
        before = snapshot(c)
        target = sorted(c.world.locations[c.world.npcs[npc].location].links)[0]
        client = FakeClient([{"action": "recall", "message": "mud"},
                             {"action": "move", "target": target}])
        r = score(c, npc, kind, client)
        assert r["action"] == "move" and r["stats"]["recalls"] == 1
        assert len(r["requests"]) == 2 and snapshot(c) == before
        done.append(r)

    source, c = replay(db, visit)
    assert done and difference(source, c) is None
    c.world.log.db.close()


@pytest.mark.parametrize("broken", [False, True])
def test_thinking_on_copies(saved_run, broken):
    db = saved_run()
    done = []

    def visit(c, npc, kind):
        if done or kind != "think":
            return
        before = snapshot(c)

        class Thought(LookClient):
            def chat(self, messages, schema):
                r = super().chat(messages, schema)
                r["because"] = ["m0", "m_missing"]
                if "recall" in schema["properties"]:
                    r["recall"] = "mud"
                r.update(notebook_me="Remember this.", notebook_people=[])
                return r

        r = score(c, npc, kind, Broken() if broken else Thought())
        assert snapshot(c) == before
        assert r["thought_parse_ok"] is not broken
        if not broken:
            assert r["citations"] == 2 and r["valid_citations"] == 1
            assert r["stats"]["recalls"] == 1
        done.append(r)

    source, c = replay(db, visit)
    assert done and difference(source, c) is None
    c.world.log.db.close()
    assert totals(done)["thought_parse_rate"] == (0 if broken else 1)


def test_run_checks_before_candidate_calls(saved_run):
    db = saved_run()
    picked = pick([db], 2, 1)
    result = run_picked(picked, LookClient())
    assert result["totals"]["turns"] == 3
    assert result["totals"]["first_try_accepted"] == 2
    assert result["totals"]["thought_parse_rate"] == 1


def test_retry_and_repeat_counts(saved_run):
    db = saved_run()
    done = []

    def visit(c, npc, kind):
        if done or kind != "act":
            return
        old = next((r for r in reversed(c.history.records)
                    if r.actor == npc and r.action == "talk"
                    and c.world.clock.tick - r.tick < 120), None)
        if old is None:
            return
        before = snapshot(c)
        repeated = {"action": "talk", "target": old.target, "message": old.message}
        repeat = score(c, npc, kind, FakeClient([repeated, repeated]))
        assert repeat["stats"]["repeats"] == repeat["stats"]["rejected"] == 2
        assert totals([repeat])["rejection_reasons"] == {"repeat guard": 2}
        retry = score(c, npc, kind, FakeClient([
            {"action": "move", "target": "loc_missing"}, {"action": "look"}]))
        assert retry["accepted_after_retry"] and not retry["fell_back_to_look"]
        assert retry["stats"]["calls"] == 2 and retry["stats"]["rejected"] == 1
        assert snapshot(c) == before
        done.append(retry)

    source, c = replay(db, visit)
    assert done and difference(source, c) is None
    c.world.log.db.close()
