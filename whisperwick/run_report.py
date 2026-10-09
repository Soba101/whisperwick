"""What the CLI adds to the sidecar after a run: the interview and where items ended up."""

from whisperwick import belief_report, interview
from whisperwick.belief_log import BeliefLog
from whisperwick.player import PLAYER_ID
from whisperwick.story import show
from whisperwick.world import World


def final_items(world: World) -> dict[str, dict]:
    """Every item's last place: a location id or a holder id (the other is None)."""
    return {
        i: {"location": item.location, "holder": item.holder}
        for i, item in sorted(world.items.items())
    }


def after_run(world: World, memories, client, stats: dict) -> dict:
    """Interview the living villagers (not the player) and note where items ended up."""
    npc_ids = [n for n in sorted(world.npcs) if world.npcs[n].alive and n != PLAYER_ID]
    return {
        "interview": interview.interview(world, memories, client, npc_ids, stats),
        "items": final_items(world),
    }


def summary_lines(
    answers: dict, names: dict[str, str], beliefs: BeliefLog | None = None
) -> list[str]:
    """One line per villager: name -> suspect name (what the model said in the interview).

    With a belief log, each line also says what the villager privately suspects,
    so a gap between what they told the interviewer and what they think shows.
    Without one (older runs, or a run where nobody thought), the lines stay as they were.
    """
    if beliefs is not None and beliefs.records:
        return [
            belief_report.interview_line(n, a, beliefs, names) for n, a in sorted(answers.items())
        ]
    lines = []
    for n, a in sorted(answers.items()):
        model = show(names, a["suspect"]) if a["suspect"] else "no idea"
        lines.append(f"  {show(names, n)} -> {model}")
    return lines
