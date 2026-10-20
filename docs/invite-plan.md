# Invites and seats

Implemented 2026-10-20. This is player-side plumbing. It changes no world rules or villagers.

## Request an invitation

Without a valid key cookie, GET `/` and `/3d` show a small offline request form (403).
The page has inline styling and script, with no external `src` or `href`.
It posts JSON to `/request`; asking never grants access or starts a game.

Names contain 1–40 characters: Unicode letters, spaces, `.`, `'`, or `-`.
Blank names are refused and outer spaces are trimmed. Notes are optional, at most 300 characters.
Unknown fields, other JSON types and invalid fields return 400.
The existing Host allowlist, JSON content-type rule and 20,000-byte body cap apply.
No key is needed for this route and no IP addresses are stored.

Requests live in `data/requests.jsonl`, next to feedback. Each line has `time`, `name`, `note`.
Names match case-insensitively. A repeat updates the note while keeping one waiting entry.
Every success says exactly `Request sent`, including repeats and requests from existing players.
There are at most 20 waiting requests. At capacity, all names receive the same plain 429 response;
a repeat can still update its note. This avoids revealing which names are waiting.
A server-wide sliding limit allows 10 POST attempts per 60 seconds, including invalid bodies.
The limiter resets when the server restarts.

## Issue and manage keys

Run commands from the project root:

```sh
uv run whisperwick requests
uv run whisperwick invite Alice --host play.example
uv run whisperwick invite --approve "Mary O'Brien"
uv run whisperwick players
uv run whisperwick revoke Alice
```

`invite --approve NAME` requires a waiting request. Plain `invite NAME` also works without one.
Both create the player, remove any matching request and print the personal HTTPS link once.
`--host` wins; otherwise the first configured `--allow-host` from the server is remembered in
`data/invite-host.json`. Without either, the link uses the explicit `YOUR-HOST` placeholder.
Duplicate player names are refused, including different case. `owner` is reserved.
A revoked name stays in the registry; this build does not rotate or recover keys.

`data/players.json` is a list of records with `name`, `key_hash`, `created`, `last_seen`, `games`,
and `revoked`. Each secret comes from `secrets.token_urlsafe(32)` and only its SHA-256 hash is saved.
The player listing omits hashes; links and raw player keys are never written to server logs.
`last_seen` is UTC and saved at most once a minute during polling; each successful new game
increments `games`. Lists show saved usage, not a live connection count.

All invite files are written to private temporary files, flushed and atomically renamed.
An advisory file lock and a process lock protect CLI/server read-modify-write operations.
With a custom run database folder, server request and player files follow feedback into that folder;
local management commands use `data/` beside the current working directory.

## Authentication and seats

`WHISPERWICK_WEB_KEY` remains the owner key; the owner name is `owner`.
Public serving still requires that key and an explicit `--allow-host`.
The cookie accepts the owner key or a key whose hash matches a non-revoked player.
Comparisons use `hmac.compare_digest`. Player authentication checks file mtime, size and inode;
revoking from the CLI takes effect on the next request. Missing or unreadable player data fails closed.

A valid `?key=` link on `/` or `/3d` sets the same HttpOnly, SameSite=Lax cookie and redirects to
the path without the key. Public-host cookies remain Secure; local HTTP cookies remain usable.
Redirects and responses are not cached and use `Referrer-Policy: no-referrer`.
The existing Host checks also cover the form, redirects, state, actions and 3D assets.

`play --web --max-games N` defaults to 5 and requires a positive number.
At capacity a sixth player gets the existing friendly 503. Finished and idle games release seats.
A player has one game: starting from another browser replaces their previous game, even at capacity.
Game cookies are checked against the authenticated identity for reading, actions and replacement.
Local play without an owner key keeps independent anonymous browser games, as before.

The 2D start page and 3D header show `Welcome, NAME` and `Seat X of N`.
The start page shows a prospective seat until Start is pressed; it does not reserve a seat.
Feedback includes a server-provided `player` name, never a client-provided identity.
The game runner's player label also carries the name outside the world state.

## Verification

Socket-free tests cover hashes on disk, owner and player keys, redirect cookie rules, revocation,
CLI approval, concurrent writes, five seats, replacement, game isolation, finished/idle release,
form validation, duplicate responses, queue and flood limits, and offline locked/2D pages.
Existing handler, feedback, role, crime and browser-script tests remain part of the checks.
Real socket and public HTTPS checks need a machine where networking is permitted.

## Outside this build

No passwords, email, password resets, automatic sign-up, or player-specific world changes.
