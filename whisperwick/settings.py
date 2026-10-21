"""Tiny settings loader.

Values come from a `.env` file in the repo root, if there is one.
Real environment variables win over the file, so a shell override always works.
"""

import os
from pathlib import Path

# The repo root is one folder above this package.
ENV_PATH = Path(__file__).parent.parent / ".env"


def read_env_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE lines. Blank lines and # comments are skipped."""
    values = {}
    if not path.is_file():
        return values  # no file is fine: the stub agent needs no settings
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def get(key: str, env_path: Path = ENV_PATH) -> str | None:
    """Look a key up: environment first, then the .env file, else None."""
    return os.environ.get(key) or read_env_file(env_path).get(key) or None


def llm_base_url(env_path: Path = ENV_PATH) -> str | None:
    return get("LLM_BASE_URL", env_path)


def llm_model(env_path: Path = ENV_PATH) -> str | None:
    return get("LLM_MODEL", env_path)


def parallel(env_path: Path = ENV_PATH) -> int:
    """How many thinking calls to send at once (WHISPERWICK_PARALLEL). Default 1 = one by one."""
    raw = get("WHISPERWICK_PARALLEL", env_path)
    if raw is None:
        return 1
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise ValueError(f"WHISPERWICK_PARALLEL must be a whole number >= 1, got {raw!r}")
    return value


def llm_server(env_path: Path = ENV_PATH) -> str:
    """Which server speaks for the model (LLM_SERVER): "ollama" (default) or "llama-server"."""
    value = get("LLM_SERVER", env_path) or "ollama"
    if value not in ("ollama", "llama-server"):
        raise ValueError(f'LLM_SERVER must be "ollama" or "llama-server", got {value!r}')
    return value


def agent_memory(env_path: Path = ENV_PATH) -> bool:
    """Do villagers get recall and a notebook (WHISPERWICK_MEMORY)? "on" (default) or "off".

    Off gives the week 5 prompts and schemas, for baseline runs.
    """
    value = get("WHISPERWICK_MEMORY", env_path) or "on"
    if value not in ("on", "off"):
        raise ValueError(f'WHISPERWICK_MEMORY must be "on" or "off", got {value!r}')
    return value == "on"


def judge_server(env_path: Path = ENV_PATH) -> str:
    """Who judges a finished run (JUDGE_SERVER): "same" (the run's chat model) or "kev"."""
    value = get("JUDGE_SERVER", env_path) or "same"
    if value not in ("same", "kev"):
        raise ValueError(f'JUDGE_SERVER must be "same" or "kev", got {value!r}')
    return value


def kev_url(env_path: Path = ENV_PATH) -> str:
    """Where Kev listens (KEV_URL). Needed only when JUDGE_SERVER=kev."""
    value = get("KEV_URL", env_path)
    if not value:
        raise ValueError("JUDGE_SERVER=kev needs KEV_URL, e.g. http://192.168.0.8:8009")
    return value


def kev_api_key(env_path: Path = ENV_PATH) -> str | None:
    """Optional key (KEV_API_KEY), sent only if the Kev server has one set."""
    return get("KEV_API_KEY", env_path)


def llm_slots(env_path: Path = ENV_PATH) -> int | None:
    """Optional act slots (LLM_SLOTS). Unset leaves server caching choices alone."""
    raw = get("LLM_SLOTS", env_path)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise ValueError(f"LLM_SLOTS must be a whole number >= 1, got {raw!r}")
    return value


def group_turns(env_path: Path = ENV_PATH) -> bool:
    """Shared conversation calls are off unless explicitly enabled."""
    value = get("WHISPERWICK_GROUP_TURNS", env_path) or "off"
    if value not in ("on", "off"):
        raise ValueError(f'WHISPERWICK_GROUP_TURNS must be "on" or "off", got {value!r}')
    return value == "on"


def recall_rank(env_path: Path = ENV_PATH) -> bool:
    """Rare-word recall ranking is off unless explicitly enabled."""
    value = get("WHISPERWICK_RECALL_RANK", env_path) or "off"
    if value not in ("on", "off"):
        raise ValueError(f'WHISPERWICK_RECALL_RANK must be "on" or "off", got {value!r}')
    return value == "on"


def stream_talk(web: bool = False, env_path: Path = ENV_PATH) -> bool:
    """Live talk defaults on for web play. Other clients keep the ordinary path."""
    value = get("WHISPERWICK_STREAM_TALK", env_path) or ("on" if web else "off")
    if value not in ("on", "off"):
        raise ValueError(f'WHISPERWICK_STREAM_TALK must be "on" or "off", got {value!r}')
    return web and value == "on"


def llm_temperature(env_path: Path = ENV_PATH) -> float:
    """Sampling temperature for villager calls (LLM_TEMPERATURE). Runs have used 0.7 since week 2.
    Week 14 E measures a higher one; the after-run judge always uses 0."""
    raw = get("LLM_TEMPERATURE", env_path)
    if raw is None:
        return 0.7
    try:
        value = float(raw)
    except ValueError:
        value = -1.0
    if not 0 <= value <= 2:
        raise ValueError(f"LLM_TEMPERATURE must be a number from 0 to 2, got {raw!r}")
    return value


def gestures(env_path: Path = ENV_PATH) -> bool:
    """Week 16 gestures and made actions are off unless WHISPERWICK_GESTURES=on (#122)."""
    value = get("WHISPERWICK_GESTURES", env_path) or "off"
    if value not in ("on", "off"):
        raise ValueError(f'WHISPERWICK_GESTURES must be "on" or "off", got {value!r}')
    return value == "on"
