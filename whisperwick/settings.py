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
