"""Thinking with villager memory: the optional recall round, and all thoughts of one moment.

Round 1 asks for the thought, and the villager may set "recall" (words to search its own
memory for). If it did, round 2 shows what was found (with real ids, so it can cite them)
and asks again without the recall field. That reply is the thought.
Searching and logging happen in the main thread, in sorted ids, so a parallel run stays
the same as a one-by-one run. Only the slow model calls overlap.
"""

from whisperwick import parallel_calls, thinking
from whisperwick.recall import Private, clean_words, search
from whisperwick.thought_schema import schema


def followup(prepared, outcome, private, world, npc_id, personality, belief_log, tick):
    """The round 2 call if the villager asked to recall, else None."""
    if not prepared.memory or not hasattr(outcome, "get") or not outcome.get("recall"):
        return None
    words = clean_words(outcome.get("recall"))
    if not words:
        return None
    found = search(private.stream, words)
    ids = [mid for mid, _ in found]
    private.log.recall(tick, npc_id, "think", words, ids)
    shown = {**prepared.shown, **dict(found)}  # real ids, so they can be cited
    note = f'You searched your memory for "{words}"; the matches are listed with their ids.'
    if not found:
        note = f'You searched your memory for "{words}" and remember nothing about it.'
    notebook = private.notebooks.lines(npc_id, world)
    prompt = thinking.messages(
        world, npc_id, personality, shown, belief_log.latest(npc_id), notebook, note
    )
    sch = schema(world, npc_id, list(shown), memory=True, recall=False)
    return thinking.Prepared(shown, prompt, sch, True, words, tuple(ids))


def think_all(
    npcs, memories, world, client, personalities, belief_log, tick, parallel, stats,
    notebooks=None, agent_log=None,
) -> None:
    """Every villager in npcs thinks at this moment. notebooks=None means memory is off."""

    def private(npc):
        return Private(memories[npc], notebooks, agent_log) if notebooks is not None else None

    prepared = {
        npc: thinking.prepare(memories[npc], npc, world, personalities.get(npc), belief_log,
                              private(npc))
        for npc in npcs
    }  # fmt: skip
    todo = [npc for npc in npcs if prepared[npc] is not None]
    outcomes = dict(zip(todo, parallel_calls.run_all(
        [lambda p=prepared[npc]: client.chat(p.messages, p.schema) for npc in todo], parallel,
    ), strict=True))  # fmt: skip
    # Round 2, only for those who recalled: found and logged in sorted ids, called together.
    again = {}
    for npc in todo:
        nxt = followup(prepared[npc], outcomes[npc], private(npc), world, npc,
                       personalities.get(npc), belief_log, tick)  # fmt: skip
        if nxt is not None:
            again[npc] = nxt
    redo = parallel_calls.run_all(
        [lambda p=again[npc]: client.chat(p.messages, p.schema) for npc in again], parallel
    )
    for npc, outcome in zip(again, redo, strict=True):
        prepared[npc], outcomes[npc] = again[npc], outcome
    for npc in todo:
        if thinking.finish(memories[npc], npc, world, tick, belief_log, prepared[npc],
                           outcomes[npc], stats, private(npc)):  # fmt: skip
            stats["thoughts"] = stats.get("thoughts", 0) + 1
