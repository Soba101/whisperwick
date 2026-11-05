"""Read-only run provenance. Nothing here is passed to a villager or the engine."""

import hashlib
import json
import subprocess
import urllib.error
import urllib.request
from concurrent.futures import Future
from pathlib import Path
from threading import Thread

import whisperwick

PROPS_TIMEOUT = 2.0
SAMPLING = ("temperature", "top_p", "top_k", "min_p", "seed", "repeat_penalty")


def git_setup() -> dict:
    """Use the installed package's checkout, even when the command ran elsewhere."""
    root = Path(whisperwick.__file__).resolve().parent

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True,
            check=True, timeout=1,
        ).stdout.strip()

    data = {"commit": None, "dirty": None}
    # A missing git command or checkout must not prevent an experiment.
    try:
        data["commit"] = git("rev-parse", "HEAD") or None
        data["dirty"] = bool(git("status", "--porcelain", "--untracked-files=no"))
    except (OSError, subprocess.SubprocessError):
        pass
    return data


def fetch_props(url: str, *, timeout: float) -> dict:
    """One GET, with no credentials added by the run client."""
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.load(response)


def allowed_props(props: dict) -> dict:
    """Copy fields explicitly. Unknown fields and the raw template never reach disk."""
    data = {}
    if isinstance(props.get("build_info"), str):
        data["build_info"] = props["build_info"]
    if isinstance(props.get("model_path"), str):
        # Accept Windows paths too; a server may run on another operating system.
        data["model_path"] = props["model_path"].replace("\\", "/").rsplit("/", 1)[-1]
    defaults = props.get("default_generation_settings", {})
    if not isinstance(defaults, dict):
        raise ValueError("bad defaults")
    # Recent servers put sampling defaults inside params; older ones put them directly here.
    params = defaults.get("params", defaults)
    if not isinstance(params, dict):
        raise ValueError("bad params")
    values = {"total_slots": props.get("total_slots"),
              "n_ctx": props.get("n_ctx", defaults.get("n_ctx"))}
    values.update({key: params[key] for key in SAMPLING if key in params})
    # Numeric fields cannot smuggle a nested response or an unexpected text value into the file.
    data.update({key: value for key, value in values.items() if type(value) in (int, float)})
    template = props.get("chat_template")
    if isinstance(template, str):
        data["chat_template_sha256"] = hashlib.sha256(template.encode()).hexdigest()
    return data


def server_setup(server: str | None, base_url: str | None, fetch=None) -> dict:
    """Bound the whole probe, including slow replies, rather than each socket read."""
    if server != "llama-server":
        return {"error": "unsupported server"}
    if not base_url:
        return {"error": "missing base URL"}
    url = base_url.rstrip("/").removesuffix("/v1") + "/props"
    result = Future()

    def probe():
        try:
            props = (fetch or fetch_props)(url, timeout=PROPS_TIMEOUT)
            if not isinstance(props, dict):
                raise ValueError("bad props")
            result.set_result(allowed_props(props))
        except Exception as error:
            # Exception messages can contain URLs or credentials. Save only fixed labels.
            if isinstance(error, TimeoutError) or isinstance(
                getattr(error, "reason", None), TimeoutError
            ):
                reason = "timeout"
            elif isinstance(error, urllib.error.HTTPError):
                reason = f"HTTP {error.code}"
            elif isinstance(error, (ValueError, TypeError)):
                reason = "invalid props"
            else:
                reason = "fetch failed"
            result.set_result({"error": reason})

    try:
        # A daemon cannot hold up the run or process exit if a server keeps sending tiny reads.
        Thread(target=probe, daemon=True).start()
        return result.result(timeout=PROPS_TIMEOUT)
    except TimeoutError:
        return {"error": "timeout"}
    except Exception:
        return {"error": "fetch failed"}


def collect_setup(
    llm_server: str | None = None, model: str | None = None, base_url: str | None = None,
    *, real_client: bool = False, temperature: float | None = None, fetch=None,
) -> dict:
    """Capture once, using the settings already resolved by the run command."""
    data = {**git_setup(), "llm_server": llm_server, "model": model}
    if temperature is not None:
        # Clients override the server default. Keep that effective value as well.
        data["temperature"] = temperature
    data["server"] = (
        server_setup(llm_server, base_url, fetch) if real_client else {"error": "no model client"}
    )
    return data
