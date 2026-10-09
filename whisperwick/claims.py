"""Check a claim before the engine acts on it. Pure: reads the world, changes nothing."""

from whisperwick.actions import CLAIM_KINDS, Intent


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
