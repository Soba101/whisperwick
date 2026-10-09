"""What the CLI adds to the sidecar after a run: the interview and where items ended up."""

from whisperwick import belief_report, interview
from whisperwick.beliefs import replay
from whisperwick.player import PLAYER_ID
from whisperwick.story import show
from whisperwick.world import World


def final_items(world: World) -> dict[str, dict]:
    """Every item's last place: a location id or a holder id (the other is None)."""
    return {
        i: {"location": item.location, "holder": item.holder}
        for i, item in sorted(world.items.items())
    }


def after_run(world: World, memories, client, stats: dict, scenario=None) -> dict:
    """Interview the living villagers (not the player) and note where items ended up.

    With the scenario, beliefs are replayed from the run's events, saved in full
    ("beliefs") and shown next to each model answer.
    """
    npc_ids = [n for n in sorted(world.npcs) if world.npcs[n].alive and n != PLAYER_ID]
    # Beliefs come from the log, not from the model, so they are safe to save as they are.
    state = replay(world.log.all(), scenario) if scenario is not None else None
    extra = {
        "interview": interview.interview(world, memories, client, npc_ids, stats, state),
        "items": final_items(world),
    }
    if state is not None:
        extra["beliefs"] = state.to_dict()
    return extra


def summary_lines(answers: dict, names: dict[str, str]) -> list[str]:
    """One line per villager: name -> suspect name.

    When the code answer is there too: 'Bob: model says Victor, beliefs say Victor 65%'.
    """
    lines = []
    for n, a in sorted(answers.items()):
        model = show(names, a["suspect"]) if a["suspect"] else "no idea"
        if "belief_suspect" not in a:  # old runs have only the model's answer
            lines.append(f"  {show(names, n)} -> {model}")
            continue
        code = belief_report.belief_text(a["belief_suspect"], a["belief_confidence"], names)
        code = code if a["belief_suspect"] else "no idea"
        lines.append(f"  {show(names, n)}: model says {model}, beliefs say {code}")
    return lines
