"""Settings tests: .env is read, and real environment variables win over it."""

from whisperwick import settings


def write_env(tmp_path, text):
    path = tmp_path / ".env"
    path.write_text(text)
    return path


def test_reads_env_file_and_skips_comments(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    path = write_env(tmp_path, "# a comment\n\nLLM_BASE_URL=http://x:1/v1\nLLM_MODEL = m1\n")
    assert settings.llm_base_url(path) == "http://x:1/v1"
    assert settings.llm_model(path) == "m1"


def test_environment_beats_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "from_env")
    path = write_env(tmp_path, "LLM_MODEL=from_file\n")
    assert settings.llm_model(path) == "from_env"


def test_missing_file_and_missing_key_give_none(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert settings.llm_base_url(tmp_path / "nope.env") is None


def test_parallel_defaults_to_one_and_reads_a_number(tmp_path, monkeypatch):
    monkeypatch.delenv("WHISPERWICK_PARALLEL", raising=False)
    assert settings.parallel(tmp_path / "nope.env") == 1
    assert settings.parallel(write_env(tmp_path, "WHISPERWICK_PARALLEL=4\n")) == 4


def test_bad_parallel_values_raise(tmp_path, monkeypatch):
    monkeypatch.delenv("WHISPERWICK_PARALLEL", raising=False)
    for bad in ("0", "-2", "two", "1.5"):
        path = write_env(tmp_path, f"WHISPERWICK_PARALLEL={bad}\n")
        try:
            settings.parallel(path)
        except ValueError as e:
            assert "WHISPERWICK_PARALLEL" in str(e)
        else:
            raise AssertionError(f"{bad} should have raised")
