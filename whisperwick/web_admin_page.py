"""Offline owner page. Escape all saved text before it reaches the document."""

from html import escape
from importlib.resources import files

from whisperwick.web_style import CSS

ADMIN_CSS = """
main,.admin-head,#notice,#personal-link{max-width:900px;margin-inline:auto}
.admin-head{display:flex;flex-wrap:wrap;align-items:center;gap:var(--s4);margin-bottom:var(--s6)}
.admin-head h1{margin-right:auto}a{color:var(--accent)}
.entry{padding-block:var(--s4);border-top:1px solid var(--line)}
.entry:last-child{padding-bottom:0}.entry p{white-space:pre-wrap}
.details{color:var(--muted)}.actions{display:flex;flex-wrap:wrap;gap:var(--s2)}
.danger{color:var(--warn)}.confirm{margin-top:var(--s3);padding:var(--s3);background:var(--soft)}
#invite{display:flex;flex-wrap:wrap;align-items:end;gap:var(--s3);margin-top:var(--s6)}
label{display:block}label input{display:block;width:100%}
#personal-link input{width:100%;margin-bottom:var(--s3)}
#notice{min-height:1.6em;overflow-wrap:anywhere}
"""
ADMIN_JS = files("whisperwick").joinpath("web_admin.js").read_text()


def text(value, empty: str = "—") -> str:
    return escape(str(value)) if value is not None and value != "" else empty


def when(value) -> str:
    # Saved times are ISO in UTC; minutes are enough to read on a phone.
    return text(value[:16].replace("T", " ") + " UTC", "Never") if value else "Never"


def button(action: str, name: str, label: str, field: str = "name") -> str:
    return (f'<button type="button" data-action="{action}" data-{field}="{text(name)}">'
            f'{label}</button>')


def section(title: str, entries: list[str], empty: str, extra: str = "") -> str:
    content = "".join(f'<article class="entry">{entry}</article>' for entry in entries)
    return f'<section class="card"><h2>{title}</h2>{content or f"<p>{empty}</p>"}{extra}</section>'


def render_admin(csrf: str, games: list[dict], maximum: int, requests: list[dict],
                 players: list[dict], feedback: list[dict]) -> str:
    seats = [f'<h3>{text(g["name"])}</h3><p>Role: {text(g["role"], "Wren (original)")} · '
             f'Crime: {text(g["crime"])} · {text(g["clock"], "Time not available")}</p>'
             + button("stop", g["id"], "Stop", "id") for g in games]
    waiting = [f'<h3>{text(r["name"])}</h3><p class="details">{when(r["time"])}</p>'
               f'<p>{text(r["note"], "No note")}</p><div class="actions">'
               + button("approve", r["name"], "Approve")
               + button("decline", r["name"], "Decline") + '</div>' for r in requests]
    people = []
    playing = {g["name"] for g in games}
    # Only live links are listed; older files may still hold revoked rows.
    for p in (p for p in players if not p["revoked"]):
        confirm = (f'<div class="confirm" hidden><p>Revoke access for {text(p["name"])}?</p>'
                   '<div class="actions">' + button("revoke", p["name"], "Yes, revoke")
                   + '<button type="button" data-cancel>Cancel</button></div></div>')
        people.append(f'<h3>{text(p["name"])}</h3><p class="details">'
                      f'Last seen: {when(p["last_seen"])} · Games: {text(p["games"])}<br>'
                      f'Playing now: {"Yes" if p["name"] in playing else "No"}</p>'
                      '<div class="actions">'
                      + (f'<button type="button" data-copy-link="{text(p["link"])}">Copy link'
                         '</button>' if p.get("link") else button("reissue", p["name"], "New link"))
                      + '<button type="button" class="danger" data-confirm>Revoke</button></div>'
                      + confirm)
    entries = [f'<h3>{text(f.get("player"), "Unknown player")}</h3>'
               f'<p class="details">{when(f.get("time"))} · {text(f.get("page"))} · '
               f'Rating: {text(f.get("rating"))} · Crime: {text(f.get("crime"))} · '
               f'Role: {text(f.get("role"))} · {text(f.get("clock"))}</p>'
               f'<p>{text(", ".join(f.get("tags", [])), "No tags")}</p>'
               f'<p>{text(f.get("text"), "No comment")}</p>' for f in feedback]
    invite = ('<form id="invite"><label>Name <input name="name" required maxlength="40" '
              'autocomplete="off"></label><button>Invite</button></form>')
    content = (section("Seats", seats, "Nobody is playing.", "")
               .replace('<h2>Seats</h2>', f'<h2>Seats</h2><p>{len(games)} of {maximum} in use</p>')
               + section("Requests", waiting, "No waiting requests.")
               + section("Players", people, "No invited players.", invite)
               + section("Recent feedback", entries, "No feedback saved."))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="csrf-token" content="{text(csrf)}"><title>Whisperwick admin</title>'
            f'<style>{CSS}{ADMIN_CSS}</style></head><body>'
            '<header class="admin-head"><h1>Whisperwick admin</h1><a href="/">Play</a>'
            '<button type="button" id="refresh">Refresh</button></header>'
            '<p id="notice" role="status" aria-live="polite"></p>'
            '<aside class="card" id="personal-link" hidden><h2>Personal link</h2>'
            '<p>Send it only to this player. You can copy it again from Players.</p>'
            '<label>New personal link <input id="link-value" readonly autocomplete="off"></label>'
            '<div class="actions"><button type="button" id="copy">Copy</button>'
            '<button type="button" id="dismiss">Dismiss</button></div>'
            '<p id="copy-status" role="status"></p></aside>'
            f'<main id="admin-content">{content}</main><script>{ADMIN_JS}</script></body></html>')
