"""The candidate's first prompt must equal the normal loop's first prompt."""

import pytest
from test_llm_sim import LookClient
from test_screen_replay import source_fixture  # noqa: F401 (shared fixture)

from whisperwick.screen_replay import difference, replay
from whisperwick.screen_score import score
from whisperwick.screen_source import ReplayClient


@pytest.mark.parametrize("memory", [True, False])
def test_first_prompts_match_the_loop(saved_run, monkeypatch, memory):
    db = saved_run(memory)
    done, pending = set(), []
    original = ReplayClient.chat

    class Candidate(LookClient):
        def chat(self, messages, schema):
            pending.append((messages, schema))
            return super().chat(messages, schema)

    def visit(c, npc, kind):
        if kind not in done:
            done.add(kind)
            score(c, npc, kind, Candidate())

    def compare(self, messages, schema):
        # Thinking callbacks run inside chat; act callbacks run before it.
        reply = original(self, messages, schema)
        if pending:
            assert len(pending) == 1
            assert pending.pop() == (messages, schema)
        return reply

    monkeypatch.setattr(ReplayClient, "chat", compare)
    source, c = replay(db, visit)
    assert done == {"act", "think"} and not pending
    assert difference(source, c) is None
    c.world.log.db.close()
