"""Act prompt text in Week 7 order."""

from collections.abc import Sequence

from whisperwick import belief_text
from whisperwick.llm_intent import exits_and_people, item_lines
from whisperwick.memory_view import memory_block
from whisperwick.repeat_guard import ActionHistory
from whisperwick.world import World


def people_label(world: World, person_id: str) -> str:
    """e.g. 'npc_bob (Bob, blacksmith)'. A held person also shows who holds them."""
    npc = world.npcs[person_id]
    held = f", held by {world.npcs[npc.held_by].name}" if npc.held_by else ""
    return f"{person_id} ({npc.name}, {npc.occupation}{held})"


def build_messages(
    world: World,
    npc_id: str,
    memories: Sequence[str] = (),
    feedback: str | None = None,
    # Week 4, all optional: with none of them the prompt has no character or belief.
    personality: str | None = None,
    belief: dict | None = None,  # this villager's latest record in the belief log
    history: ActionHistory | None = None,
    # Week 6, optional: private notebook and recall lines, and whether recall is offered.
    private_lines: Sequence[str] = (),
    recall: bool = False,
    evidence: Sequence[str] = (),  # starting evidence, shown under its own heading (#56)
) -> list[dict]:
    """One compact system message: who I am, where I am, who and what is around."""
    me = world.npcs[npc_id]
    exits, people = exits_and_people(world, npc_id)
    here = world.locations[me.location]
    # Hybrid llama-server reuses only exact repeats, not part of a prompt.
    # Tested 2026-10-15: a shared 1,700-token start reused 0 tokens.
    # Reordering gave no speed and changed model input; keep Week 7 order
    # so behaviour stays comparable.
    lines = [
        f"You are {me.name} ({me.id}), the village {me.occupation}.",
        # Who I am as a person, then what I last worked out, in my own words.
        *belief_text.character_lines(personality),
        *belief_text.belief_lines(world, belief, npc_id),
        "Reply only with JSON. Use exact ids, never names.",
        # The trial run invented ledgers, letters and gold. Facts belong to the engine.
        "Only claim things you saw or were told. Never invent objects, records or events.",
        # Spell out what each action needs. The schema alone cannot say
        # "move takes an exit, talk takes a person".
        "Actions: move (target = an exit id), talk (target = a person id, plus a message),"
        " look (target = null),"
        " take/drop (item = an item id), give (item + target = a person id),"
        " show (item, target = a person id, or null for everyone here)."
        + (" recall (message = words to search your own memory for)." if recall else ""),
        *belief_text.custody_lines(world, npc_id),
        f"Time: {world.clock.label()}.",
        f"You are at {here.id} ({here.name}).",
        "Exits: " + ", ".join(f"{e} ({world.locations[e].name})" for e in exits),
        "People here: "
        + (", ".join(people_label(world, p) for p in people) or "nobody"),
        "Items on the ground here: " + item_lines(world, world.items_at(here.id)),
        "You carry: " + item_lines(world, world.items_held(npc_id)),
    ]  # fmt: skip
    # A body is not a person you can talk to, but you can see it. Say so plainly.
    bodies = world.bodies_at(here.id)
    if bodies:
        lines.append("Lying dead here: " + ", ".join(f"{b} ({world.npcs[b].name})" for b in bodies))
    # What I already said to the people in front of me, so I can see when I repeat myself.
    lines += belief_text.last_words(world, history, npc_id, people)
    lines.append(belief_text.CLAIM_RULE)
    lines += memory_block(evidence, memories)
    # Notebook and what a recall just found: private to this villager.
    lines += private_lines
    if feedback:
        # The engine's own words, so the model can fix its mistake.
        lines.append(f"Your last action was rejected: {feedback}. Choose again.")
    # A short user turn as well: chat models answer more reliably
    # when there is a question to reply to, not only a system message.
    return [
        {"role": "system", "content": "\n".join(lines)},
        {"role": "user", "content": "What do you do now?"},
    ]

