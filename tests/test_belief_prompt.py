"""What the model sees each turn (character, own thoughts, trust) and the claim it can make."""

from pathlib import Path

from helpers import SCENARIO, fresh_world

from whisperwick import llm_agent
from whisperwick.belief_log import BeliefLog
from whisperwick.llm_client import FakeClient
from whisperwick.llm_sim import run_llm
from whisperwick.player_script import load_script
from whisperwick.repeat_guard import ActionHistory
from whisperwick.scenario import load_scenario

PLAYERS = Path(__file__).parent.parent / "players"
PERSONALITY = load_scenario(SCENARIO).personality

# A record as thinking.py makes it, with only what the prompt reads.
BOB_THOUGHT = {
    "npc": "npc_bob",
    "suspect": "npc_victor",
    "sureness": "fairly sure",
    "thoughts": "I saw him hurry away from the Town Hall.",
    "trust": [
        {"person": "npc_victor", "level": "low", "why": "he talks too smoothly"},
        {"person": "npc_hal", "level": "high", "why": "an honest guard"},
    ],
}


def prompt(w, npc, personality=None, belief=None, history=None):
    return llm_agent.build_messages(
        w, npc, personality=personality, belief=belief, history=history
    )[0]["content"]


def reply(**kw):
    base = {"action": "look", "target": None, "item": None, "message": None}
    return {**base, "accuses": None, "defends": None, **kw}


# ---- the prompt ----


def test_character_comes_right_after_identity_then_own_thoughts():
    w = fresh_world()
    lines = prompt(w, "npc_bob", PERSONALITY["npc_bob"], BOB_THOUGHT).split("\n")
    assert lines[0].startswith("You are Bob")
    assert lines[1] == "Your character: " + PERSONALITY["npc_bob"]
    assert lines[2] == (
        "What you think right now: you suspect Victor (npc_victor), fairly sure. "
        "I saw him hurry away from the Town Hall."
    )
    assert lines[3] == (
        "How you feel about people: Victor (npc_victor) low: he talks too smoothly; "
        "Hal (npc_hal) high: an honest guard"
    )


def test_no_numbers_from_code_and_no_points_to_you_marks():
    w = fresh_world()
    text = prompt(w, "npc_victor", PERSONALITY["npc_victor"], BOB_THOUGHT)
    assert "%" not in text and "points to you" not in text and "Your goal" not in text


def test_nobody_suspected_and_the_killer_knowing_it_was_them():
    w = fresh_world()
    none = {**BOB_THOUGHT, "suspect": None, "thoughts": "I have no idea.", "trust": []}
    text = prompt(w, "npc_bob", belief=none)
    assert (
        "What you think right now: you don't suspect anyone of anything yet. I have no idea."
        in text
    )
    assert "How you feel" not in text
    me = {**BOB_THOUGHT, "npc": "npc_victor", "suspect": "npc_victor", "thoughts": "Stay calm."}
    assert "you know you are guilty. Stay calm." in prompt(w, "npc_victor", belief=me)
    # The villager's own words for what it suspects someone of.
    bob = {**BOB_THOUGHT, "of_what": "killing the mayor"}
    assert "you suspect Victor (npc_victor) of killing the mayor," in prompt(
        w, "npc_bob", belief=bob
    )


def test_no_thought_yet_means_no_belief_lines():
    w = fresh_world()
    text = prompt(w, "npc_bob", PERSONALITY["npc_bob"])
    assert "Your character:" in text and "What you think" not in text
    plain = prompt(w, "npc_bob")
    assert "Your character" not in plain and "last words" not in plain


def test_claim_rule_is_always_there_and_reworded():
    text = prompt(fresh_world(), "npc_bob")
    assert (
        "If your words openly accuse someone, set accuses to their id. "
        "If your words openly defend someone, set defends to their id. "
        "Otherwise leave both null." in text
    )


def test_last_words_show_the_three_most_recent_to_people_here():
    w = fresh_world()
    history = ActionHistory()
    for minute, msg in enumerate(["one", "two", "three", "four"]):
        history.record(w.clock.tick + minute, _talk("npc_bob", "npc_victor", msg))
    history.record(w.clock.tick, _talk("npc_bob", "npc_sarah", "not here"))  # Sarah is away
    text = prompt(w, "npc_bob", history=history)
    assert "Your last words here:" in text
    assert '"two"' in text and '"three"' in text and '"four"' in text
    assert '"one"' not in text and "not here" not in text


def _talk(actor, target, message, **kw):
    from whisperwick.actions import Intent

    return Intent(actor=actor, action="talk", target=target, message=message, **kw)


# ---- the schema and decide() ----


def test_schema_has_flat_claim_fields():
    w = fresh_world()
    props = llm_agent.intent_schema(w, "npc_bob")["properties"]
    assert props["accuses"]["enum"] == [*sorted(w.npcs), None]
    assert props["defends"]["enum"] == [*sorted(w.npcs), None]
    required = llm_agent.intent_schema(w, "npc_bob")["required"]
    assert "accuses" in required and "defends" in required


def test_claim_is_built_only_for_talk():
    w = fresh_world()
    talk = reply(action="talk", target="npc_victor", message="Hal did it")
    both = {"accuses": "npc_hal"}
    got = llm_agent.decide(w, "npc_bob", FakeClient([{**talk, **both}]))
    assert got.claim.kind == "accuses" and got.claim.subject == "npc_hal"
    stats = {}
    one = llm_agent.decide(
        w, "npc_bob", FakeClient([{**talk, "defends": "npc_hal"}]), stats=stats
    )
    assert one.claim.kind == "defends" and "errors" not in stats
    # A claim on a look is model noise: dropped quietly.
    look = llm_agent.decide(w, "npc_bob", FakeClient([reply(**both)]), stats=stats)
    assert look.action == "look" and look.claim is None and "errors" not in stats


def test_old_clients_without_claim_fields_still_work():
    w = fresh_world()
    old = {"action": "talk", "target": "npc_victor", "message": "hi"}
    intent = llm_agent.decide(w, "npc_bob", FakeClient([old]))
    assert intent.action == "talk" and intent.claim is None


# ---- whole runs ----

THOUGHT = {"thoughts": "quiet", "suspect": None, "sureness": "unsure", "because": [], "trust": []}


class ClaimClient:
    """Bob says Hal is the killer to Victor once; everyone else looks."""

    def __init__(self):
        self.prompts = []

    def chat(self, messages, schema):
        if "thoughts" in schema["properties"]:
            return THOUGHT
        self.prompts.append(messages[0]["content"])
        if "(npc_bob)" in messages[0]["content"]:
            return reply(
                action="talk",
                target="npc_victor",
                message="Hal did it",
                accuses="npc_hal",
            )
        return reply()


def test_model_claim_is_logged_and_remembered_by_the_hearer():
    w = fresh_world()
    memories, _ = run_llm(w, ClaimClient(), 1, personalities=PERSONALITY)
    [talk] = [e for e in w.log.all() if e.type == "talk"]
    assert talk.data["claim"] == {"kind": "accuses", "subject": "npc_hal"}
    # The claim is a fact about what was said, not a change in what Victor believes.
    [heard] = [m for m in memories["npc_victor"].memories if "Hal did it" in m.text]
    assert "[claim: accuses Hal (npc_hal)]" in heard.text and heard.event_id == talk.id


def test_run_prompts_carry_character_and_the_latest_own_thought():
    w, log, client = fresh_world(), BeliefLog(), ClaimClient()
    log.add({**BOB_THOUGHT, "after_event": 0})
    run_llm(w, client, 1, personalities=PERSONALITY, belief_log=log)
    bob = next(p for p in client.prompts if "(npc_bob)" in p)
    assert "Your character: Blunt and stubborn" in bob and "you suspect Victor" in bob
    alice = next(p for p in client.prompts if p.startswith("You are Alice"))
    assert "Warm and chatty" in alice and "What you think" not in alice


def test_player_claim_is_logged_without_changing_anyones_mind_by_code():
    w, client = fresh_world(), ClaimClient()
    player = load_script(PLAYERS / "blame_hal.yaml")
    run_llm(w, client, 3, player=player)
    claims = [e for e in w.log.all() if e.actor == "player" and e.data.get("claim")]
    assert claims  # the lie is on the record, and the world did not stop it
