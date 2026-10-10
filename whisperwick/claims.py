"""Check a claim before the engine acts on it. Pure: reads the world, changes nothing."""

from whisperwick.actions import CLAIM_KINDS, Intent

# Logs written before the rename used these words. Readers map them to the new kinds.
OLD_KINDS = {"killer": "accuses", "innocent": "defends"}


def kind_of(claim: dict) -> str:
    """The claim's kind as 'accuses' or 'defends', reading old logs too."""
    return OLD_KINDS.get(claim["kind"], claim["kind"])


def claim_words(claim: dict, subject_name: str) -> str:
    """e.g. 'accuses Hal (npc_hal)'. One wording for every reader."""
    return f"{kind_of(claim)} {subject_name}"


def claim_problem(world, intent: Intent) -> str | None:
    """Why the claim on this intent is not allowed, or None if it is fine (or absent)."""
    claim = intent.claim
    if claim is None:
        return None
    # Only talk carries words, so only talk may carry a claim.
    if intent.action != "talk":
        return f"a claim can only go with talk, not {intent.action}"
    if claim.kind not in CLAIM_KINDS:
        return f"unknown claim kind {claim.kind}"
    # Any person in the world will do, dead or alive. Whether it is true is not our job.
    if claim.subject not in world.npcs:
        return f"unknown claim subject {claim.subject}"
    return None
