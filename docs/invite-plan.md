# Invites and seats (draft 2026-10-20, waiting on Donovan)

Player-side plumbing only. Nothing here touches the world or any villager.

## What to build
1. **Request form** on the locked page (no key): name, optional note. Saved to data/requests.jsonl on the Mac.
   Same name twice keeps one request; at most 20 waiting, so the form cannot be flooded. Nobody gets in by asking.
2. **Per-person keys.** `whisperwick requests` lists requests; `whisperwick invite --approve NAME` (or
   `whisperwick invite NAME` for someone who never asked) makes a key, stores only its hash in
   data/players.json and prints the personal link once. The existing web key stays the owner key.
3. **Seats.** `--max-games` setting (default 5, today it is 3). Idle and finished games free their seat, as now.
   One game per person at a time.
4. **Manage.** `whisperwick players` (name, last seen, games, playing now) and `whisperwick revoke NAME`
   (that person's cookie stops working at once). Feedback entries (#107) carry the player's name.

## Not in this build
- Open sign-up with passwords, password resets, email: too much risk on a public link for a playtest.
- Any per-player change to the game itself.

## Checks
- Unit tests: hashed keys only on disk; a revoked key is refused; the 6th game waits; the form refuses
  floods and long fields; the owner key still works; Host and cookie rules unchanged (web_auth tests).
- The 2D page stays offline (no external src or href).
