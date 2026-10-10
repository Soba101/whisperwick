"""Parse one line typed by the human player. Pure: no world, no printing."""

from whisperwick.actions import Intent
from whisperwick.player import PLAYER_ID

DEFAULT_WAIT = 10  # minutes, when "wait" has no number

HELP = """Commands:
  look                       show the room again (free)
  move <loc>                 walk to a place, e.g. move loc_inn
  talk <npc> <message...>    say something to someone here
  tell <npc> <kind> <person> <message...>
                             talk, and claim the person (kind: accuses or defends)
                             e.g. tell npc_bob accuses npc_hal I saw him
  take <item>                pick up an item from the ground
  drop <item>                put an item down
  give <item> <npc>          hand an item to someone here
  show <item> [npc]          let people see what you carry
  wait [minutes]             let time pass (default 10)
  help                       this text
  quit                       leave the game"""


def parse_command(line: str) -> tuple[str, object] | None:
    """Return (kind, data) or None for garbage.

    kind is "act" (data = Intent), "wait" (data = minutes), or "look", "help", "quit".
    """
    words = line.split()
    if not words:
        return None
    cmd, args = words[0].lower(), words[1:]

    def act(**fields) -> tuple[str, object]:
        return "act", Intent(actor=PLAYER_ID, action=cmd, **fields)

    if cmd in ("look", "help", "quit") and not args:
        return cmd, None
    if cmd == "wait" and len(args) <= 1:
        if not args:
            return "wait", DEFAULT_WAIT
        return ("wait", int(args[0])) if args[0].isdigit() and int(args[0]) > 0 else None
    if cmd == "move" and len(args) == 1:
        return act(target=args[0])
    if cmd == "talk" and len(args) >= 2:
        # Everything after the npc id is the message, spaces kept as typed words.
        return act(target=args[0], message=" ".join(args[1:]))
    if cmd == "tell" and len(args) >= 4:
        # A tell is a talk with a claim. The engine checks the kind and the person, not us,
        # so a typo gets the same clear rejection as anywhere else.
        cmd = "talk"
        claim = {"kind": args[1].lower(), "subject": args[2]}
        return act(target=args[0], message=" ".join(args[3:]), claim=claim)
    if cmd in ("take", "drop") and len(args) == 1:
        return act(item=args[0])
    if cmd == "give" and len(args) == 2:
        return act(item=args[0], target=args[1])
    if cmd == "show" and len(args) in (1, 2):
        return act(item=args[0], target=args[1] if len(args) == 2 else None)
    return None
