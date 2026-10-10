"""The after-run judge's questions: one small prompt and one JSON schema each.

Prompts only state what was said or remembered and ask. They never say what the
answer should be, and the judge never sees the scenario's secret.
"""

SYSTEM = "You grade pieces of a village story log. Reply only with the JSON asked for."

YES_NO = {
    "type": "object",
    "properties": {"answer": {"type": "string", "enum": ["yes", "no"]}},
    "required": ["answer"],
}
SCORE = {
    "type": "object",
    "properties": {"score": {"type": "integer", "minimum": 1, "maximum": 5}},
    "required": ["score"],
}
MISREAD = {
    "type": "object",
    "properties": {
        "misread": {"type": "boolean"},
        "what": {"type": ["string", "null"], "maxLength": 200},
    },
    "required": ["misread", "what"],
}


def messages(text: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]


def bullets(lines: list[str]) -> str:
    return "\n".join(f"- {t}" for t in lines)


def claim_text(speaker: str, to: str, message: str, kind: str, subject: str) -> str:
    verb = "accuse" if kind == "accuses" else "defend"
    return (
        f'{speaker} said to {to}: "{message}"\n\n'
        f"Question: do these words really {verb} {subject}? Answer yes or no."
    )


def support_text(subject: str, of_what: str | None, memories: list[str]) -> str:
    return (
        f"A villager remembers:\n{bullets(memories)}\n\n"
        f"The villager suspects {subject} of: {of_what or 'something unstated'}.\n\n"
        "Question: how well do these memories support suspecting that person of that? "
        "Score 1 (not at all) to 5 (fully)."
    )


def misread_text(thought: str, memories: list[str]) -> str:
    return (
        f"A villager remembers:\n{bullets(memories)}\n\n"
        f'The villager then thinks: "{thought}"\n\n'
        "Question: does the thought state something as fact that the memories contradict "
        "or misread? If so, say what in one short sentence."
    )


def coherence_text(day_story: str) -> str:
    return (
        f"Here is one day of a village story, as a log:\n\n{day_story}\n\n"
        "Question: how coherent and easy to follow is this as a story? "
        "Score 1 (confused) to 5 (clear)."
    )
