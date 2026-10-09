"""Trace a belief back to where it came from: who believes it, and via whom.

Pure functions over a BeliefState, so no model and no world are needed.
build_trace() makes a plain dict (also the --json output); format_trace() prints it.
"""

from whisperwick import story
from whisperwick.beliefs import BeliefState, Source
from whisperwick.clock import Clock

MAX_DEPTH = 6  # a rumour chain longer than this is cut off, with a note
STEP = 3  # spaces added for each hop in the printed chain


def node(src: Source, state: BeliefState, subject: str, path: tuple, depth: int) -> dict:
    """One link of a chain: a source, plus what the teller's own sources were."""
    out = {
        "kind": src.type,
        "by": src.by,
        "event_id": src.event_id,
        "tick": src.tick,
        "when": Clock(src.tick).label(),
        "note": src.note,
        "sources": [],
    }
    if src.type != "told":
        return out  # a "saw" source ends the chain: it is first-hand
    # Event ids only go down along a chain, but guard anyway: depth and repeats.
    key = (src.by, src.event_id)
    if depth >= MAX_DEPTH or key in path:
        out["cut"] = True
        return out
    # What did the teller know *before* telling? (compared by event id)
    before = state.sources_before(src.by, subject, src.event_id)
    if not before:
        # Nothing behind it: the teller made it up. This is where a lie starts.
        out["sources"] = [{"kind": "own", "by": src.by, "sources": []}]
    else:
        out["sources"] = [node(s, state, subject, (*path, key), depth + 1) for s in before]
    return out


def tellers(nodes: list[dict]) -> list[str]:
    """Every distinct teller in a chain, in sorted order."""
    found: set[str] = set()
    for n in nodes:
        if n["kind"] == "told":
            found.add(n["by"])
        found |= set(tellers(n["sources"]))
    return sorted(found)


def build_trace(state: BeliefState, subject: str) -> dict:
    """Everyone who believes `subject` did it, strongest belief first."""
    holders = [h for h, subs in state.conf.items() if subs.get(subject, 0) > 0]
    holders.sort(key=lambda h: (-state.conf[h][subject], h))
    believers = []
    for h in holders:
        chain = [node(s, state, subject, (), 0) for s in state.sources.get(h, {}).get(subject, [])]
        believers.append(
            {
                "id": h,
                "confidence": state.conf[h][subject],
                # The believer's own trust in each teller, at the end of the run.
                "trusts": {t: state.trust.get(h, t) for t in tellers(chain)},
                "sources": chain,
            }
        )
    # Trust in the player, for every villager who holds any belief or trust at all.
    everyone = sorted((set(state.conf) | set(state.trust.pairs)) - {state.trust.player_id})
    return {
        "subject": subject,
        "believers": believers,
        "trust_in_player": {h: state.trust.get(h, state.trust.player_id) for h in everyone},
    }


def label(names: dict[str, str], who: str) -> str:
    """'Bob (npc_bob)', or just the id if the name is the id or unknown."""
    name = story.show(names, who)
    return who if name == who else f"{name} ({who})"


def source_lines(n: dict, names: dict[str, str], indent: int) -> list[str]:
    pad = " " * indent
    if n["kind"] == "own":
        return [f"{pad}{story.show(names, n['by'])} had no source: made up (a guess or a lie)"]
    where = f"event {n['event_id']}, {n['when']}" if n["event_id"] is not None else "at the start"
    if n["kind"] == "saw":
        return [f"{pad}<- saw: {n['note']} ({where})"]
    # An "innocent" claim is also a told source, but it pulls the other way: say so.
    against = " (said innocent)" if n.get("note") == "said innocent" else ""
    lines = [f"{pad}<- told by {label(names, n['by'])}{against}, {where}"]
    if n.get("cut"):
        lines.append(f"{pad}{' ' * STEP}... chain cut here (too long, or a loop)")
    for child in n["sources"]:
        lines += source_lines(child, names, indent + STEP)
    return lines


def format_trace(trace: dict, names: dict[str, str]) -> str:
    out = [f"Who believes {label(names, trace['subject'])} killed the mayor?"]
    for b in trace["believers"]:
        line = f"{label(names, b['id'])} {b['confidence']:.0%}"
        if b["trusts"]:
            who = ", ".join(f"{story.show(names, t)} {v:.0%}" for t, v in b["trusts"].items())
            line += f"   trusts {who}"
        out.append(line)
        for src in b["sources"]:
            out += source_lines(src, names, 2)
    if not trace["believers"]:
        out.append("Nobody.")
    out += ["", "Trust in the player:"]
    out += [f"  {label(names, h)} {v:.0%}" for h, v in trace["trust_in_player"].items()]
    return "\n".join(out)
