"""Week 4 task 3: what the model sees (beliefs, trust, goal) and the claim it can make."""

from pathlib import Path

from helpers import SCENARIO, fresh_world

from whisperwick import llm_agent
from whisperwick.beliefs import BeliefState
from whisperwick.events import Event
from whisperwick.llm_client import FakeClient
from whisperwick.llm_sim import run_llm
from whisperwick.player_script import load_script
from whisperwick.repeat_guard import ActionHistory
from whisperwick.scenario import load_scenario

PLAYERS = Path(__file__).parent.parent / "players"


def setup():
    sc = load_scenario(SCENARIO)
    return fresh_world(), BeliefState.from_scenario(sc), sc.goals


def prompt(w, npc, beliefs=None, goals=None, history=None):
    goal = (goals or {}).get(npc)
    return llm_agent.build_messages(w, npc, beliefs=beliefs, goal=goal, history=history)[0][
        "content"
    ]


def reply(**kw):
    base = {"action": "look", "target": None, "item": None, "message": None}
    return {**base, "claim_kind": None, "claim_subject": None, **kw}


# ---- the prompt ----


def test_prompt_shows_goal_beliefs_trust_and_rule():
    w, beliefs, goals = setup()
    text = prompt(w, "npc_bob", beliefs, goals)
    assert "Your goal: Keep your forge running" in text
    assert "What you believe about the murder:" in text
    assert "- Victor (npc_victor) did it: 50%. Why: saw Victor hurrying" in text
    # Victor and the player are here with Bob. Sorted by id: npc_victor before player.
    assert "Trust in people here: Victor 50%, Wren 30%" in text
    assert "add claim_kind (killer or innocent) and claim_subject" in text


def test_goal_comes_right_after_identity_and_before_beliefs():
    w, beliefs, goals = setup()
    lines = prompt(w, "npc_bob", beliefs, goals).split("\n")
    assert lines[0].startswith("You are Bob")
    assert lines[1].startswith("Your goal:")
    assert lines[2] == "What you believe about the murder:"


def test_victor_sees_you_did_it():
    w, beliefs, goals = setup()
    text = prompt(w, "npc_victor", beliefs, goals)
    assert "- You did it: 100%." in text
    assert "Victor (npc_victor) did it" not in text


def test_beliefs_list_is_top_3_highest_first_and_groups_tellers():
    w, beliefs, _ = setup()
    for subject, c in [("npc_hal", 0.9), ("npc_sarah", 0.4), ("npc_alice", 0.1)]:
        beliefs._set("npc_bob", subject, c)
    for i in (1, 2):
        beliefs._add("npc_bob", "npc_hal", _told("npc_alice", i))
    lines = prompt(w, "npc_bob", beliefs).split("\n")
    bullets = [x for x in lines if x.startswith("- ") and "did it" in x]
    assert len(bullets) == 3
    assert bullets[0].startswith("- Hal (npc_hal) did it: 90%. Why: told by Alice (npc_alice) x2")
    assert bullets[1].startswith("- Victor") and bullets[2].startswith("- Sarah")


def _told(by, event_id):
    from whisperwick.beliefs import Source

    return Source("told", by, event_id, 0, "said killer")


def test_items_pointing_to_me_are_marked_but_not_others():
    w, beliefs, goals = setup()
    victor = prompt(w, "npc_victor", beliefs, goals)
    assert (
        "item_boots (muddy boots: Victor's boots, caked in fresh mud) - this points to you!"
        in victor
    )
    # Hal also sees the knife, but it points to Victor, not to Hal.
    assert "points to you" not in prompt(w, "npc_hal", beliefs, goals)


def test_no_beliefs_means_the_old_prompt():
    w = fresh_world()
    text = prompt(w, "npc_bob")
    for word in ["Your goal", "believe", "Trust in", "points to you", "claim_kind", "last words"]:
        assert word not in text


def test_last_words_show_the_three_most_recent_to_people_here():
    w, beliefs, _ = setup()
    history = ActionHistory()
    for minute, msg in enumerate(["one", "two", "three", "four"]):
        history.record(w.clock.tick + minute, _talk("npc_bob", "npc_victor", msg))
    history.record(w.clock.tick, _talk("npc_bob", "npc_sarah", "not here"))  # Sarah is away
    text = prompt(w, "npc_bob", beliefs, history=history)
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
    assert props["claim_kind"]["enum"] == ["killer", "innocent", None]
    assert props["claim_subject"]["enum"] == [*sorted(w.npcs), None]
    required = llm_agent.intent_schema(w, "npc_bob")["required"]
    assert "claim_kind" in required and "claim_subject" in required


def test_claim_is_built_only_for_talk_with_both_fields():
    w = fresh_world()
    talk = reply(action="talk", target="npc_victor", message="Hal did it")
    both = {"claim_kind": "killer", "claim_subject": "npc_hal"}
    got = llm_agent.decide(w, "npc_bob", FakeClient([{**talk, **both}]))
    assert got.claim.kind == "killer" and got.claim.subject == "npc_hal"
    # Only one field set: dropped, not an error.
    stats = {}
    one = llm_agent.decide(
        w, "npc_bob", FakeClient([{**talk, "claim_kind": "killer"}]), stats=stats
    )
    assert one.action == "talk" and one.claim is None and "errors" not in stats
    # A claim on a look is model noise: dropped quietly.
    look = llm_agent.decide(w, "npc_bob", FakeClient([reply(**both)]), stats=stats)
    assert look.action == "look" and look.claim is None and "errors" not in stats


def test_old_clients_without_claim_fields_still_work():
    w = fresh_world()
    old = {"action": "talk", "target": "npc_victor", "message": "hi"}
    intent = llm_agent.decide(w, "npc_bob", FakeClient([old]))
    assert intent.action == "talk" and intent.claim is None


# ---- whole runs ----


class ClaimClient:
    """Bob says Hal is the killer to Victor once; everyone else looks."""

    def chat(self, messages, schema):
        if "thoughts" in schema["properties"]:
            return {"thoughts": "quiet"}
        if "(npc_bob)" in messages[0]["content"]:
            return reply(
                action="talk",
                target="npc_victor",
                message="Hal did it",
                claim_kind="killer",
                claim_subject="npc_hal",
            )
        return reply()


def test_model_claim_updates_hearers_beliefs():
    w, beliefs, goals = setup()
    run_llm(w, ClaimClient(), 1, beliefs=beliefs, goals=goals)
    assert beliefs.confidence("npc_victor", "npc_hal") > 0
    [talk] = [e for e in w.log.all() if e.type == "talk"]
    assert talk.data["claim"] == {"kind": "killer", "subject": "npc_hal"}
    [src] = beliefs.sources["npc_victor"]["npc_hal"]
    assert src.by == "npc_bob" and src.event_id == talk.id


def test_run_without_beliefs_is_unchanged():
    a, b = fresh_world(), fresh_world()
    run_llm(a, ClaimClient(), 5)
    run_llm(b, ClaimClient(), 5, beliefs=BeliefState.from_scenario(load_scenario(SCENARIO)))
    # Beliefs only watch: the world is the same either way.
    assert a.state_hash() == b.state_hash()


class LookClient:
    def chat(self, messages, schema):
        if "thoughts" in schema["properties"]:
            return {"thoughts": "quiet"}
        return reply()


def test_player_claim_updates_bobs_beliefs_in_a_run():
    w, beliefs, goals = setup()
    player = load_script(PLAYERS / "blame_hal.yaml")
    run_llm(w, LookClient(), 3, player=player, beliefs=beliefs, goals=goals)
    # Trust in the player is 0.3, so Bob moves a little: 0.3 * 0.5 = 0.15.
    assert beliefs.confidence("npc_bob", "npc_hal") == 0.15
    [src] = beliefs.sources["npc_bob"]["npc_hal"]
    assert src.by == "player"


def test_plain_talk_without_a_claim_changes_no_belief():
    # A plain talk changes nothing.
    _, beliefs, _ = setup()
    before = beliefs.to_dict()
    data = {"to": "npc_victor", "message": "hi"}
    talk = Event(id=1, tick=0, type="talk", actor="npc_bob", location="loc_market", data=data)
    beliefs.apply(talk)
    assert beliefs.to_dict() == before
