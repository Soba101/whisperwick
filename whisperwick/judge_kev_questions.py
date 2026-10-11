"""The same four judge questions, worded for Kev (yes/no, choice-free, 5-level scores).

Like judge_questions.py, they only state what was said or remembered and ask. They never
say what the answer should be, and the judge never sees the scenario's secret.
"""

from whisperwick.judge_questions import bullets

SUPPORT_LEVELS = ["not at all", "weakly", "partly", "mostly", "fully"]
COHERENCE_LEVELS = [
    "confused, hard to follow",
    "mostly unclear",
    "partly clear",
    "mostly clear",
    "clear, easy to follow",
]


def noul(instructions: str) -> dict:
    return {"type": "noul", "instructions": instructions}


def score(instructions: str, levels: list[str]) -> dict:
    return {"type": "score", "instructions": instructions, "criteria": levels}


def claim_state(speaker: str, to: str, message: str) -> str:
    return f'{speaker} said to {to}: "{message}"'


def claim_question(kind: str, subject: str) -> dict:
    verb = "accuse" if kind == "accuses" else "defend"
    return noul(f"Do these words really {verb} {subject}?")


def thought_state(memories: list[str], thought: str, subject: str | None, of_what: str | None):
    text = f"A villager remembers:\n{bullets(memories)}\n\n"
    if subject:
        text += f"The villager suspects {subject} of: {of_what or 'something unstated'}.\n\n"
    return text + f'The villager then thinks: "{thought}"'


def support_question() -> dict:
    ask = "How well do these memories support suspecting that person of that?"
    return score(ask, SUPPORT_LEVELS)


def misread_question() -> dict:
    return noul(
        "Does the thought state something as fact that the memories contradict or misread? "
        "For example, calling a living person dead."
    )


def coherence_state(day_story: str) -> str:
    return f"Here is one day of a village story, as a log:\n\n{day_story}"


def coherence_question() -> dict:
    return score("How coherent and easy to follow is this as a story?", COHERENCE_LEVELS)
