"""LLM_TEMPERATURE: unset keeps the long-standing 0.7; bad values stop the run before it starts."""

import pytest

from whisperwick import settings


def test_default_and_custom_temperature(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("")
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    assert settings.llm_temperature(env) == 0.7
    monkeypatch.setenv("LLM_TEMPERATURE", "1.0")
    assert settings.llm_temperature(env) == 1.0


@pytest.mark.parametrize("bad", ["hot", "-0.1", "3"])
def test_bad_temperature_is_refused(tmp_path, monkeypatch, bad):
    monkeypatch.setenv("LLM_TEMPERATURE", bad)
    with pytest.raises(ValueError):
        settings.llm_temperature(tmp_path / ".env")


def test_week16_actions_are_off_by_default(tmp_path, monkeypatch):
    # Gestures crowded out talk in the week 16 check (#122), so they are opt-in.
    from helpers import fresh_world

    from whisperwick import made_prompt
    from whisperwick.llm_intent import actions_for

    monkeypatch.delenv("WHISPERWICK_GESTURES", raising=False)
    assert settings.gestures(tmp_path / ".env") is False
    made_prompt.ENABLED = False
    assert "gesture" not in actions_for(fresh_world(), "npc_bob")
    assert made_prompt.action_text() == "" and made_prompt.properties(None, [], [], []) == {}
