"""#42 and #43: authority can name an absent person, and custody facts reach the prompts."""

from helpers import fresh_world

from whisperwick import belief_text, llm_agent, llm_intent, thinking
from whisperwick.memory import Memory


def do(actor, action, **kw):
    return {"actor": actor, "action": action, **kw}


class Pick:
    """A fake client that always returns one fixed reply."""

    def __init__(self, reply):
        self.reply = reply

    def chat(self, messages, schema):
        return dict(self.reply)


def targets(w, npc):
    return llm_intent.intent_schema(w, npc)["properties"]["target"]["enum"]


def prompt(w, npc):
    return llm_agent.build_messages(w, npc)[0]["content"]


def held_victor():
    w = fresh_world()
    assert w.move("npc_victor", "loc_town_hall").ok
    assert w.act(do("npc_hal", "arrest", target="npc_victor")).ok
    return w


def test_authority_can_name_absent_living_person_not_the_dead():
    w = fresh_world()
    t = targets(w, "npc_hal")
    assert "npc_victor" in t and "npc_mayor" not in t and "npc_hal" not in t
    assert len(t) == len(set(t)) and t[-1] is None


def test_non_authority_schema_target_unchanged():
    w = fresh_world()
    exits, people = llm_intent.exits_and_people(w, "npc_bob")
    assert targets(w, "npc_bob") == [*exits, *people, None]


def test_arrest_of_absent_target_is_rejected_and_changes_nothing():
    w = fresh_world()
    stats: dict = {}
    reply = {"action": "arrest", "target": "npc_victor", "item": None, "message": None}
    llm_agent.act(w, "npc_hal", Pick(reply), stats=stats)
    assert stats["rejected"] == 2  # both tries refused: Victor is not here
    assert w.npcs["npc_victor"].held_by is None
    assert not any(e.type == "arrest" for e in w.log.all())
    assert "is not here" in w.act(do("npc_hal", "arrest", target="npc_victor")).reason


def test_action_prompt_lists_held_people_with_places():
    w = held_victor()
    w.npcs["npc_victor"].location = "loc_inn"  # forced state: held person elsewhere
    text = prompt(w, "npc_hal")
    assert "You are holding: Victor (npc_victor) at " in text
    assert "The person must be here with you." in text
    assert "You are holding" not in prompt(fresh_world(), "npc_hal")


def think_prompt(w, npc):
    shown = {"m1": Memory(tick=0, text="a day", importance=1, kind="obs", event_id=None)}
    return thinking.messages(w, npc, None, shown, None)[0]["content"]


def test_thinking_prompt_has_custody_facts_only():
    w = held_victor()
    assert "You are being held by Hal." in think_prompt(w, "npc_victor")
    assert "You are holding: Victor (npc_victor)" in think_prompt(w, "npc_hal")
    assert belief_text.WORDS_RULE not in think_prompt(w, "npc_hal")
    quiet = think_prompt(fresh_world(), "npc_hal")
    assert "You are being held" not in quiet and "You are holding" not in quiet
