"""The words a thought is asked in. Split out of thinking.py (file size)."""

from whisperwick import aims, belief_text
from whisperwick.memory import Memory
from whisperwick.thought_people import people_ids

NOTEBOOK_ASK = (
    "You may update your private notebook: a few words about yourself and one line per "
    "person, or leave it as it is (null keeps it)."
)
# Only on the first ask: the recall field is offered there, so say what it does.
RECALL_ASK = (
    "If you want to search your own memory first, put the words in recall: you will see "
    "what you find and think again. Otherwise recall is null."
)


def messages(
    world, npc_id, personality, shown: dict[str, Memory], previous,
    notebook: list[str] | None = None, recall_note: str | None = None,
) -> list[dict]:
    """In character, first person. Without this the model answers as an assistant.

    notebook=None means villager memory is off: no notebook lines and no notebook sentence.
    """
    me = world.npcs[npc_id]
    # No line saying "the mayor was killed": a real villager only knows that if it saw
    # the body or was told. What it knows is in its memories, nowhere else.
    _, trusted = people_ids(world, npc_id)
    lines = [
        f"You are {me.name} ({me.id}), the village {me.occupation}. Stay in character.",
        *belief_text.character_lines(personality),
        "People you may have met: " + ", ".join(belief_text.who(world, n) for n in trusted),
        "Your memories, each with its id:",
        *(f"[{mid}] {m.text}" for mid, m in shown.items()),
    ]
    if recall_note:
        lines.append(recall_note)
    lines += notebook or []
    # #43: plain custody facts only (Sarah was held all day, yet her thoughts said "released").
    lines += belief_text.custody_facts(world, npc_id)
    if previous:
        lines += ["Your last thoughts (you may change your mind):"]
        lines += belief_text.belief_lines(world, previous, npc_id, with_aim=False)
        # Here the aim is offered back to be continued, changed or dropped.
        if aims.active(previous):
            lines.append(f"Your aim: {aims.active(previous)}")
    lines += [
        "Reply only with JSON. Use exact ids, never names.",
        "Only rely on the memories listed. Never invent objects, records or events.",
    ]
    # An open question: what is going on, as far as I know? Nothing here hints at the plot.
    ask = (
        "Think to yourself, in first person. What do you make of what has been happening? "
        "Who, if anyone, do you truly believe has done something bad, of what, and how sure "
        "are you? Which of your memories make you think so (give their ids)? "
        "Do you mean to accuse anyone out loud? If so, who? "
        + aims.ASK + " "
        "And how do you feel about the people you have met, and why?"
        + ("" if notebook is None else " " + NOTEBOOK_ASK)
        # Memory on and no recall yet = the first ask, the one that offers recall.
        + ("" if notebook is None or recall_note else " " + RECALL_ASK)
    )
    return [
        {"role": "system", "content": "\n".join(lines)},
        {"role": "user", "content": ask},
    ]
