"""The notebook: stored, trimmed and shown only to its owner. Written only by thoughts."""

from helpers import fresh_world
from test_recall import thought

from whisperwick import llm_agent
from whisperwick.agent_log import AgentLog
from whisperwick.belief_log import BeliefLog
from whisperwick.llm_client import FakeClient
from whisperwick.memory import MemoryStream
from whisperwick.notebook import ME_MAX_CHARS, PERSON_MAX_CHARS, Notebooks
from whisperwick.recall import Private
from whisperwick.thought_memory import think_all

OTHERS = ["npc_hal", "npc_victor"]


def test_apply_trims_replaces_removes_and_keeps_on_null():
    nb = Notebooks()
    nb.apply("npc_bob", {"notebook_me": "  calm\n  and  quiet " + "x" * 400,
                         "notebook_people": [{"person": "npc_hal", "line": "honest\nguard"},
                                             {"person": "npc_victor", "line": "y" * 300},
                                             {"person": "npc_nobody", "line": "ignored"}]},
             OTHERS)  # fmt: skip
    book = nb.get("npc_bob")
    assert book["me"].startswith("calm and quiet") and len(book["me"]) == ME_MAX_CHARS
    assert book["people"]["npc_hal"] == "honest guard"
    assert len(book["people"]["npc_victor"]) == PERSON_MAX_CHARS
    assert "npc_nobody" not in book["people"]
    # null keeps, a new line replaces, an empty line removes
    nb.apply("npc_bob", {"notebook_me": None,
                         "notebook_people": [{"person": "npc_hal", "line": "less sure"},
                                             {"person": "npc_victor", "line": ""}]},
             OTHERS)  # fmt: skip
    assert book["me"] is not None and book["people"] == {"npc_hal": "less sure"}
    nb.apply("npc_bob", {"notebook_me": ""}, OTHERS)
    assert book["me"] is None


def test_at_most_six_people_per_thought_and_bad_shapes_are_ignored():
    nb = Notebooks()
    entries = [{"person": f"npc_{i}", "line": "x"} for i in range(8)]
    nb.apply("npc_bob", {"notebook_people": entries}, [f"npc_{i}" for i in range(8)])
    assert len(nb.get("npc_bob")["people"]) == 6
    nb.apply("npc_bob", {"notebook_people": "junk", "notebook_me": 5}, OTHERS)
    nb.apply("npc_bob", {"notebook_people": [3, None]}, OTHERS)


def test_lines_are_empty_when_nothing_written_and_name_the_people():
    world, nb = fresh_world(), Notebooks()
    assert nb.lines("npc_bob", world) == []
    nb.apply("npc_bob", {"notebook_me": "careful", "notebook_people": [
        {"person": "npc_hal", "line": "trusted"}]}, OTHERS)  # fmt: skip
    assert nb.lines("npc_bob", world) == [
        "Your private notebook (only you can see it):",
        "About you: careful",
        "- Hal (npc_hal): trusted",
    ]  # fmt: skip


def test_a_thought_writes_the_notebook_and_only_its_owner_sees_it():
    world, s, nb = fresh_world(), MemoryStream(), Notebooks()
    s.add(1, "I saw Victor.", 5)
    log = BeliefLog()
    reply = thought(because=[], suspect=None, notebook_me="I worry.",
                    notebook_people=[{"person": "npc_hal", "line": "kind"}])  # fmt: skip
    think_all(["npc_bob"], {"npc_bob": s}, world, FakeClient([reply]), {}, log, 600, 1, {},
              nb, AgentLog())  # fmt: skip
    assert log.records[0]["notebook"] == {"me": "I worry.", "people": {"npc_hal": "kind"}}
    # Bob sees it when acting; Victor (same notebooks, other owner) does not
    bob, victor = FakeClient([{"action": "look"}]), FakeClient([{"action": "look"}])
    for npc, client in (("npc_bob", bob), ("npc_victor", victor)):
        llm_agent.act(world, npc, client, [], {}, private=Private(s, nb, AgentLog()))
    assert "About you: I worry." in bob.calls[0]["messages"][0]["content"]
    assert "notebook" not in victor.calls[0]["messages"][0]["content"]
    # and Bob sees it when thinking again, with the neutral sentence in the ask
    again = FakeClient([thought(because=[], suspect=None)])
    think_all(["npc_bob"], {"npc_bob": s}, world, again, {}, log, 700, 1, {}, nb, AgentLog())
    assert "- Hal (npc_hal): kind" in again.calls[0]["messages"][0]["content"]
    assert "private notebook" in again.calls[0]["messages"][1]["content"]
    assert "notebook_me" in again.calls[0]["schema"]["required"]


def test_notebook_is_not_changed_by_a_failed_thought():
    nb, s = Notebooks(), MemoryStream()
    s.add(1, "x", 1)
    bad = thought(suspect="npc_ghost", notebook_me="should not stick")
    think_all(["npc_bob"], {"npc_bob": s}, fresh_world(), FakeClient([bad]), {}, BeliefLog(), 5,
              1, {}, nb, AgentLog())  # fmt: skip
    assert nb.lines("npc_bob", fresh_world()) == []
