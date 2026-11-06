"""The journal uses only the feed it is given: grouping, one clash, nothing extra."""

from whisperwick.web_journal import build

PEOPLE = {"npc_wren": "Wren", "npc_alice": "Alice", "npc_bob": "Bob", "npc_cara": "Cara",
          "npc_secret": "Zed"}
PLACES = {"loc_inn": "Inn", "loc_market": "Market"}
FEED = [
    '09:00  Inn:    Alice -> Wren: "Bob was at the Market at 9:15."',
    '09:05  Inn:    Cara -> Wren: "I saw Bob at the Inn at 9am."',
    '09:10  Inn:    Cara -> Wren: "Alice was at the Inn at 9am."',
    "09:20  Market: Bob takes the lamp",
]
KNOWN = {"items": [{"name": "lamp", "carried": False, "place": {"name": "Market"},
                    "clock": "Day 1 09:20"}],
         "visits": [{"place": {"id": "loc_inn", "name": "Inn"}, "clock": "Day 1 09:00"}]}


def journal():
    return build(FEED, KNOWN, PEOPLE, PLACES, "npc_wren")


def test_lines_group_by_person_and_skip_the_player():
    groups = {g["id"]: g["lines"] for g in journal()["about"]}
    assert groups["npc_bob"] == [FEED[0], FEED[1], FEED[3]]
    assert groups["npc_alice"] == [FEED[2]]  # only what is said about her, not who spoke
    assert "npc_wren" not in groups


def test_one_contradiction_shows_both_lines_without_a_verdict():
    found = journal()["contradictions"]
    assert len(found) == 1
    assert found[0]["id"] == "npc_bob" and found[0]["hour"] == "09:00"
    assert {found[0]["a"], found[0]["b"]} == {FEED[0], FEED[1]}


def test_nothing_from_outside_the_feed_appears():
    text = str(journal())
    assert "Zed" not in text and "npc_secret" not in text
    assert [i["name"] for i in journal()["items"]] == ["lamp"]
    assert journal()["visits"] == KNOWN["visits"]
    assert build([], {"items": [], "visits": []}, PEOPLE, PLACES, "npc_wren")["about"] == []
