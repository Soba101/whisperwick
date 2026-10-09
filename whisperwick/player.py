"""The player actor.

The player is a normal NPC record with this id. The engine has no special case:
World.act treats its intents like anyone's, and villagers see and remember them.
Only the agent side differs: no code agent ever drives it (see stub_agent.py and
llm_sim.py), because the player is a human or, later, a script.
"""

PLAYER_ID = "player"


class PlayerSource:
    """What the run loop needs from whoever plays the player (a script or a human).

    turn(world) is called at the start of every minute, before the NPCs act, also at
    night. It returns the intents for this minute (maybe none), or None to quit.
    report(intent, result) is called after the engine answers each intent, so the
    source can show a rejection reason or a look result.
    """

    def turn(self, world) -> list | None:
        raise NotImplementedError

    def report(self, intent, result) -> None:
        pass
