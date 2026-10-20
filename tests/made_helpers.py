"""Small action definitions shared by the new engine checks."""

from helpers import fresh_world

HIDE = {"action": "make", "name": "tuck_away", "params": ["item"],
        "needs": ["holds_item"], "does": ["hide_item_here"]}
REVEAL = {"action": "make", "name": "uncover", "params": [], "needs": [],
          "does": ["reveal_hidden_here"]}


def make(world, definition=HIDE, actor="npc_victor", **extra):
    return world.act({"actor": actor, **definition, **extra})


def hidden_world():
    world = fresh_world()
    assert make(world, use={"item": "item_boots"}).ok
    return world
