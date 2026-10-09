"""Claims: a talk may carry {kind, subject}. Well formed is enough: lies are allowed."""

from pathlib import Path

import pytest
from helpers import SCENARIO, fresh_world, run_ticks

from whisperwick.actions import CLAIM_KINDS
from whisperwick.memory import Memories
from whisperwick.player import PLAYER_ID
from whisperwick.player_commands import parse_command
from whisperwick.player_script import load_script, parse_steps
from whisperwick.scenario import load_scenario
from whisperwick.story import format_story, names_from

PLAYERS = Path(__file__).parent.parent / "players"
HAL = {"kind": "killer", "subject": "npc_hal"}


def tell(claim, actor=PLAYER_ID, action="talk", target="npc_bob"):
    # The player starts at the market with Bob and Victor, so this talk is legal.
    return {"actor": actor, "action": action, "target": target, "message": "hi", "claim": claim}


def test_valid_claim_is_logged_with_witnesses():
    w = fresh_world()
    r = w.act(tell(HAL))
    assert r.ok
    assert r.event.data == {"to": "npc_bob", "message": "hi", "claim": HAL}
    # Bob is the listener, Victor overhears.
    assert {"npc_bob", "npc_victor"} <= set(r.event.witnesses)


def test_kinds_and_subjects_that_are_allowed():
    w = fresh_world()
    assert CLAIM_KINDS == ("killer", "innocent")
    # Innocent is fine, the player is a fine subject, and so is the dead mayor.
    assert w.act(tell({"kind": "innocent", "subject": "npc_victor"})).ok
    assert w.act(tell({"kind": "killer", "subject": PLAYER_ID})).ok
    dead = next(n.id for n in w.npcs.values() if not n.alive)
    assert w.act(tell({"kind": "killer", "subject": dead})).ok


@pytest.mark.parametrize(
    "bad",
    [
        tell({"kind": "thief", "subject": "npc_hal"}),  # unknown kind
        tell({"kind": "killer", "subject": "npc_nobody"}),  # not a person
        tell({"kind": "killer", "subject": "Hal"}),  # a display name, not an id
        tell(HAL, action="look", target=None),  # not a talk
        tell(HAL, action="move", target="loc_inn"),  # not a talk
        tell({"kind": "killer"}),  # malformed
        tell({"kind": "killer", "subject": "npc_hal", "extra": 1}),  # extra field
    ],
)
def test_bad_claims_are_rejected_and_change_nothing(bad):
    w = fresh_world()
    before, count = w.state_hash(), len(w.log.all())
    r = w.act(bad)
    assert not r.ok and r.reason and r.event is None
    assert w.state_hash() == before and len(w.log.all()) == count


def test_talk_without_claim_has_no_claim_key():
    w = fresh_world()
    r = w.act({"actor": PLAYER_ID, "action": "talk", "target": "npc_bob", "message": "hi"})
    assert r.ok and r.event.data == {"to": "npc_bob", "message": "hi"}


def test_memory_and_story_text_show_the_claim():
    w, mem = fresh_world(), Memories()
    event = w.act(tell(HAL)).event
    mem.observe(event, w)
    assert mem["npc_bob"].memories[0].text.endswith('"hi" [claim: Hal (npc_hal) is the killer]')
    story = format_story([event], names_from(load_scenario(SCENARIO)))
    assert 'Wren -> Bob: "hi" [claim: Hal is the killer]' in story
    # Innocent reads differently, and no claim adds nothing.
    other = w.act(tell({"kind": "innocent", "subject": "npc_victor"})).event
    assert "[claim: Victor (npc_victor) is innocent]" in _text(w, other)
    plain = w.act({"actor": PLAYER_ID, "action": "talk", "target": "npc_bob", "message": "x"})
    assert "claim" not in _text(w, plain.event)


def _text(w, event):
    mem = Memories()
    mem.observe(event, w)
    return mem["npc_bob"].memories[0].text


def test_script_steps_carry_a_claim():
    steps = [{"at": "1 08:00", "action": "talk", "target": "npc_bob", "message": "x", "claim": HAL}]
    _, script = parse_steps({"steps": steps})
    assert next(iter(script.values()))[0].claim.model_dump() == HAL
    # The shipped example uses it on both talks.
    talks = [i for v in load_script(PLAYERS / "blame_hal.yaml").script.values() for i in v]
    assert [i.claim.model_dump() for i in talks if i.action == "talk"] == [HAL, HAL]


def test_tell_command_makes_a_talk_with_a_claim():
    kind, intent = parse_command("tell npc_bob killer npc_hal I saw  him")
    assert kind == "act" and intent.action == "talk" and intent.actor == PLAYER_ID
    assert (intent.target, intent.message) == ("npc_bob", "I saw him")
    assert intent.claim.model_dump() == HAL
    # Too short is garbage. A bad kind parses, then the engine rejects it with a reason.
    assert parse_command("tell npc_bob killer npc_hal") is None
    bad = parse_command("tell npc_bob thief npc_hal hi")[1]
    assert not fresh_world().act(bad).ok


def test_claims_do_not_break_determinism():
    def run():
        w = fresh_world(7)
        assert w.act(tell(HAL)).ok
        return run_ticks(w, 50)

    assert run() == run()
