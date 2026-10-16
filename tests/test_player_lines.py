"""The player's feed lines: the web shows only the words, the terminal keeps claim tags."""

from helpers import fresh_world

from whisperwick.events import Event
from whisperwick.player import PLAYER_ID
from whisperwick.player_terminal import player_lines


def talk_with_claim() -> Event:
    # Bob speaks to the player and tags it as an accusation of Victor.
    return Event(tick=600, type="talk", actor="npc_bob", location="loc_market",
                 data={"to": PLAYER_ID, "message": "I saw Victor leave.",
                       "claim": {"kind": "accuses", "subject": "npc_victor"}},
                 witnesses=[PLAYER_ID])  # fmt: skip


def test_terminal_lines_keep_the_claim_tag():
    (line,) = player_lines(fresh_world(), [talk_with_claim()])
    assert "[claim:" in line and "I saw Victor leave." in line


def test_web_lines_show_only_the_words_and_leave_the_event_alone():
    event = talk_with_claim()
    (line,) = player_lines(fresh_world(), [event], claims=False)
    assert "[claim:" not in line and "I saw Victor leave." in line
    # The tag is still on the event itself: measures and memories still use it.
    assert event.data["claim"]["subject"] == "npc_victor"
