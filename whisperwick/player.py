"""The player actor.

The player is a normal NPC record with this id. The engine has no special case:
World.act treats its intents like anyone's, and villagers see and remember them.
Only the agent side differs: no code agent ever drives it (see stub_agent.py and
llm_sim.py), because the player is a human or, later, a script.
"""

PLAYER_ID = "player"
