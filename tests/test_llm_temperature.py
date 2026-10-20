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
