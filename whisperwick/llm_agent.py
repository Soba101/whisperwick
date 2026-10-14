"""An NPC that is driven by a language model.

The model only proposes an Intent. The engine (World.act) still decides
what really happens. We never trust the model's output without that check.
"""

from collections.abc import Sequence

from pydantic import ValidationError

from whisperwick.act_prompt import build_messages, people_label  # noqa: F401 (re-exported)
from whisperwick.actions import ActionResult, Intent
from whisperwick.llm_client import LLMError
from whisperwick.llm_intent import intent_schema
from whisperwick.memory_view import (  # noqa: F401  (re-exported)
    memory_block,
    memory_lines,
    memory_parts,
)
from whisperwick.recall import Private, Recall, act_lines, clean_words, search
from whisperwick.repeat_guard import ActionHistory, repeat_reason
from whisperwick.world import World


def decide(
    world: World,
    npc_id: str,
    client,
    memories: Sequence[str] = (),
    feedback: str | None = None,
    stats: dict | None = None,
    personality: str | None = None,
    belief: dict | None = None,
    history: ActionHistory | None = None,
    private_lines: Sequence[str] = (),
    recall: bool = False,
    evidence: Sequence[str] = (),
    slot: int | None = None,
) -> Intent | Recall:
    """Ask the model for an intent. Anything unusable becomes a harmless look.

    stats, if given, counts {"errors"} and keeps "last_error", so failures are not silent.
    It also counts "error_reasons" by kind ("HTTP 400", "timeout", ...) and prints one line each.
    With recall=True the model may ask to search its memory: that comes back as a Recall.
    """
    try:
        reply = dict(
            client.chat(
                build_messages(
                    world, npc_id, memories, feedback, personality, belief, history,
                    private_lines, recall, evidence,
                ),
                intent_schema(world, npc_id, recall),
                **({"slot": slot} if slot is not None else {}),
            )
        )
        if recall and reply.get("action") == "recall":
            if stats is not None and stats.get("errors_in_a_row"):
                stats["errors_in_a_row"] = 0  # the model answered
            return Recall(clean_words(reply.get("message")))
        # The two flat fields become one Claim, but only on a talk. On any other action
        # they are model noise and are dropped quietly, not counted as an error.
        # pop(key, None) keeps old clients that never send the fields working.
        accuses, defends = reply.pop("accuses", None), reply.pop("defends", None)
        if reply.get("action") == "talk":
            if accuses and defends and stats is not None:
                # A tag can only carry one claim; we measure how often both are set.
                stats["claim_both"] = stats.get("claim_both", 0) + 1
            if accuses:
                reply["claim"] = {"kind": "accuses", "subject": accuses}
            elif defends:
                reply["claim"] = {"kind": "defends", "subject": defends}
        # The actor is filled in by code. The model never chooses who it is.
        intent = Intent(actor=npc_id, **reply)
    except (LLMError, ValidationError, TypeError) as e:
        if stats is not None:
            stats["errors"] = stats.get("errors", 0) + 1
            stats["last_error"] = str(e)
            # Why, in a short stable label, so a run can count the kinds of failure.
            reason = getattr(e, "reason", "bad reply")
            reasons = stats.setdefault("error_reasons", {})
            reasons[reason] = reasons.get(reason, 0) + 1
            # One line per error in the run output, so nothing fails silently.
            print(f"{world.clock.label()}  model error for {npc_id}: {reason}", flush=True)
            # Counted so the run can stop when the model server is gone (#34).
            stats["errors_in_a_row"] = stats.get("errors_in_a_row", 0) + 1
        return Intent(actor=npc_id, action="look")
    if stats is not None and stats.get("errors_in_a_row"):
        stats["errors_in_a_row"] = 0  # the model answered, so the server is alive
    return intent


def act(
    world: World,
    npc_id: str,
    client,
    memories: Sequence[str] = (),
    stats: dict | None = None,
    personality: str | None = None,
    belief: dict | None = None,
    history: ActionHistory | None = None,
    private: Private | None = None,  # recall and notebook; None = neither (memory off)
    evidence: Sequence[str] = (),
    slot: int | None = None,
) -> ActionResult:
    """Decide and act. One retry with the engine's reason, then fall back to look.

    stats, if given, counts {"calls", "rejected", "errors", "repeats"}
    so a run can report its rejection rate. A recall is not an action: it is not sent to the
    world, not a call and not a rejection; it is counted as stats["recalls"].
    """
    stats = stats if stats is not None else {}
    feedback = None
    notebook = private.notebooks.lines(npc_id, world) if private else []
    for _ in range(2):
        intent = decide(
            world, npc_id, client, memories, feedback, stats, personality, belief, history,
            notebook, recall=private is not None, evidence=evidence, slot=slot,
        )
        if isinstance(intent, Recall):
            # Search its own memory, then ask again in the same turn. Recall is not offered
            # on that second ask, so a turn holds at most one recall.
            found = search(private.stream, intent.words)
            stats["recalls"] = stats.get("recalls", 0) + 1
            private.log.recall(world.clock.tick, npc_id, "act", intent.words, [i for i, _ in found])
            intent = decide(
                world, npc_id, client, memories, feedback, stats, personality, belief, history,
                [*notebook, *act_lines(intent.words, found)], evidence=evidence, slot=slot,
            )
        # Repeat guard (#12): refuse a pointless repeat before the engine sees it.
        # It counts as a rejection, so the one-retry flow below stays the same.
        reason = repeat_reason(world, history, intent) if history is not None else None
        if reason:
            stats["repeats"] = stats.get("repeats", 0) + 1
            result = ActionResult(False, reason)
        else:
            result = world.act(intent)
            if result.ok and history is not None:
                history.record(world.clock.tick, intent)
        stats["calls"] = stats.get("calls", 0) + 1
        if result.ok:
            return result
        stats["rejected"] = stats.get("rejected", 0) + 1
        feedback = result.reason
    return world.act(Intent(actor=npc_id, action="look"))
