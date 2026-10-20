"""2026-10-21: a requester comes back later and is signed in once approved."""

from http.cookies import SimpleCookie

from invite_helpers import manager, request

from whisperwick import web_auth
from whisperwick.invite_players import Players
from whisperwick.invite_requests import Requests, clean_code


def ticket_of(result):
    cookie = SimpleCookie(result["headers"]["Set-Cookie"])
    return cookie[web_auth.TICKET_COOKIE].value


def visit(store, games, waiting, ticket, path="/"):
    # The helper sends key cookies only, so add the ticket as an extra Cookie header.
    return request(store, games, path, waiting=waiting,
                   headers={"Cookie": f"{web_auth.TICKET_COOKIE}={ticket}"})


def test_waiting_then_approved_signs_in_and_declined_is_closed(tmp_path):
    store, games = Players(tmp_path), manager()
    waiting = Requests(tmp_path)
    sent = request(store, games, "/request", {"name": "Cara", "note": ""}, waiting=waiting)
    ticket = ticket_of(sent)
    assert clean_code(sent["headers"]["X-Request-Code"]) == ticket
    assert b"waiting for approval" in visit(store, games, waiting, ticket)["body"]
    store.invite("Cara", approve=True)
    signed = visit(store, games, waiting, ticket)
    assert signed["code"] == 302 and signed["headers"]["Location"] == "/"
    # Declined (or never approved) tickets only see the closed message.
    other = ticket_of(request(store, games, "/request", {"name": "Dee", "note": ""},
                              waiting=waiting))
    waiting.decline("Dee")
    assert b"not approved" in visit(store, games, waiting, other)["body"]


def test_a_repeat_request_cannot_take_over_someone_elses_approval(tmp_path):
    store, games = Players(tmp_path), manager()
    waiting = Requests(tmp_path)
    first = ticket_of(request(store, games, "/request", {"name": "Eve", "note": ""},
                              waiting=waiting))
    thief = ticket_of(request(store, games, "/request", {"name": "eve", "note": "me"},
                              waiting=waiting))
    store.invite("Eve", approve=True)
    assert store.claim(first) and store.claim(thief) is None


def test_codes_from_another_device_are_checked_for_shape():
    assert clean_code("abcd-efg-hjk") == "ABCDEFGHJK"
    for bad in ("", "short", "ABCD-EFG-HJ0", None, 5):
        assert clean_code(bad) is None
