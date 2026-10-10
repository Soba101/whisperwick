"""Aims: a short thing a villager says it wants to do, in its own words.

The model decides everything here. No code ever assigns, suggests or scores an aim.
The code only trims the text, checks the status word, and says what is still active.
An aim is private to its villager and logged for analysis. It is never a world event
and never part of World state or state_hash.
"""

AIM_MAX_CHARS = 120  # a few words, e.g. "find out where Victor was last night"
STATUSES = ["new", "continuing", "done", "dropped"]
ACTIVE = ["new", "continuing"]  # an aim being worked on; done and dropped are over

# Open and neutral on purpose: "nothing in particular" is a fine answer.
ASK = (
    "Is there anything you want to do in the next while? If so, say it in a few words, "
    "and whether it is new, the same as before, done, or dropped. "
    "Nothing in particular is a fine answer."
)


def schema_properties() -> dict:
    """The two schema fields. Both are required, but both may be null."""
    return {
        "aim": {"type": ["string", "null"], "maxLength": AIM_MAX_CHARS},
        "aim_status": {"enum": [*STATUSES, None]},
    }


def checked(reply: dict) -> tuple[str | None, str | None]:
    """(aim, aim_status) from a reply. Raises ValueError on a status that is not allowed.

    Rules, kept simple:
    - An aim with no status counts as new.
    - "new" or "continuing" with no aim means nothing: the status is dropped too.
    - "done" or "dropped" may come with the aim they refer to, or with no aim at all.
    """
    # .get(): older fake clients send neither field.
    status = reply.get("aim_status")
    if status is not None and status not in STATUSES:
        raise ValueError(f"unknown aim_status {status}")
    # The server does not always enforce maxLength, so trim here and flatten newlines.
    aim = " ".join(str(reply.get("aim") or "").split())[:AIM_MAX_CHARS] or None
    if aim is None and status in ACTIVE:
        status = None
    if aim is not None and status is None:
        status = "new"
    return aim, status


def active(record: dict | None) -> str | None:
    """The aim text if the villager's latest record has one still being worked on."""
    # .get(): records written before aims existed have no such keys.
    if record and record.get("aim_status") in ACTIVE:
        return record.get("aim")
    return None
