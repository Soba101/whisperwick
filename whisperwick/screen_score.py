"""Score only parser and engine facts, on state that the replay never owns."""

from copy import deepcopy

from whisperwick import llm_agent, thinking, thought_memory
from whisperwick.agent_log import AgentLog
from whisperwick.events import EventLog
from whisperwick.llm_client import LLMError
from whisperwick.memory import MemoryStream, memory_id
from whisperwick.recall import Private
from whisperwick.screen_usage import MeasuredClient


def copy_world(world):
    """Give each candidate a disposable world so replay stays unchanged."""
    log = EventLog(":memory:")
    try:
        # A sqlite connection cannot be copied. The memo replaces it without touching the source.
        copied = deepcopy(world, {id(world.log): log})
        # Thoughts use the latest event id; prompts may inspect earlier events too.
        for event in world.log.all():
            log.append(event)
        return copied
    except BaseException:
        log.db.close()
        raise


def score(c, npc, kind, client):
    """Use the normal turn handlers to measure a candidate on isolated state."""
    world = copy_world(c.world)
    # Recall, notes and repeat checks must start from the saved private context.
    stream = deepcopy(c.memories.get(npc, MemoryStream()))
    books, beliefs = deepcopy(c.notebooks), deepcopy(c.belief_log)
    # Copied beliefs must never append to the original run file.
    beliefs.path = None
    history = deepcopy(c.history)
    private = Private(stream, books, AgentLog()) if c.agent_memory else None
    measured = MeasuredClient(client)
    stats = {}
    reasons = []
    original_act = world.act

    def checked_act(intent):
        """Capture engine rejection reasons without changing its decisions."""
        result = original_act(intent)
        if not result.ok:
            reasons.append(result.reason)
        return result

    # Observe the ordinary retry path rather than duplicating its rules here.
    world.act = checked_act
    record = {"tick": world.clock.tick, "npc": npc, "kind": kind}
    try:
        if kind == "act":
            evidence, lines = llm_agent.memory_parts(stream, world.clock.tick, world, npc)
            result = llm_agent.act(
                world, npc, measured, lines, stats, c.personalities.get(npc),
                beliefs.latest(npc), history, private, evidence,
            )
            # A safe fallback must not make an unusable reply count as accepted.
            failed = bool(stats.get("errors") or stats.get("rejected", 0) == stats["calls"])
            record.update(first_try_accepted=stats["calls"] == 1 and not failed,
                          accepted_after_retry=stats["calls"] == 2 and not failed,
                          fell_back_to_look=failed,
                          action=result.event.type if result.event else "look")
        elif kind == "think":
            prepared = thinking.prepare(
                stream, npc, world, c.personalities.get(npc), beliefs, private)
            if prepared is None:
                raise ValueError(f"no memories for picked thought: {npc}")

            def ask(p):
                """Pass failures to the thought handler so normal error accounting applies."""
                try:
                    return measured.chat(p.messages, p.schema)
                except (LLMError, KeyError, TypeError, ValueError) as exc:
                    return exc

            outcome = ask(prepared)
            # Thoughts may search memory once before producing their final answer.
            nxt = thought_memory.followup(prepared, outcome, private, world, npc,
                                          c.personalities.get(npc), beliefs, world.clock.tick)
            if nxt:
                prepared, outcome = nxt, ask(nxt)
                stats["recalls"] = 1
            # Check citation ids against this villager's stream rather than the whole world.
            mids = outcome.get("because", []) if isinstance(outcome, dict) else []
            mids = mids if isinstance(mids, list) else []
            existing = {memory_id(i) for i in range(len(stream.memories))}
            valid = sum(isinstance(mid, str) and mid in existing for mid in mids)
            record.update(citations=len(mids), valid_citations=valid)
            result = thinking.finish(stream, npc, world, world.clock.tick, beliefs, prepared,
                                     outcome, stats, private)
            record["thought_parse_ok"] = result is not None
            if result is None:
                reason = getattr(outcome, "reason", "bad thought")
                stats["thought_error_reasons"] = {reason: 1}
        else:
            raise ValueError(f"unknown turn kind: {kind}")
        # Count requests separately because retries and recalls add extra calls.
        failed_parses = stats.get("errors", 0) + stats.get("thought_errors", 0)
        record.update(parse_ok=len(measured.records) - failed_parses, parse_failed=failed_parses)
        record.update(stats=stats, rejection_reasons=reasons, usage=measured.usage.summary(),
                      requests=measured.records)
        return record
    # Close the temporary database even when a candidate request fails.
    finally:
        world.log.db.close()
