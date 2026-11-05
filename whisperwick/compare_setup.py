"""Show setup provenance without requiring it in older sidecars."""


def setup_text(setup: dict | None) -> str:
    if setup is None:
        return "-"
    commit = (setup.get("commit") or "-")[:8]
    dirty = "+dirty" if setup.get("dirty") else "?" if setup.get("dirty") is None else ""
    server = setup.get("server", {})
    build = server.get("build_info", "-")
    template = (server.get("chat_template_sha256") or "-")[:8]
    temperature = setup.get("temperature", server.get("temperature", "-"))
    return (
        f"commit {commit}{dirty}, build {build}, slots {server.get('total_slots', '-')}, "
        f"n_ctx {server.get('n_ctx', '-')}, temperature {temperature}, template {template}"
    )


def lines(runs: list[dict]) -> list[str]:
    """Compare full values so shortened hashes cannot conceal a difference."""
    setups = [run["sidecar"].get("setup") for run in runs]
    out = ["Setup:"]
    out += [f"  {run['name']}: {setup_text(setup)}"
            for run, setup in zip(runs, setups, strict=True)]
    known = [setup for setup in setups if setup is not None]
    # Missing provenance is unknown, so it cannot prove that two setups differ.
    if known and any(setup != known[0] for setup in known[1:]):
        out.append("WARNING: Run setups differ; check setup before pooling results.")
    return out
