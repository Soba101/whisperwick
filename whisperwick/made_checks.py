"""Dry runs and independent invariants for made actions. All checks are pure code."""

from copy import deepcopy

from whisperwick.events import EventLog
from whisperwick.items import check_items
from whisperwick.made_shapes import argument_problem, shape_problem
from whisperwick.made_steps import allowed_changes, needs_problem, run_step


def copy_world(world):
    """Deep-copy state, including any future secret fields, without copying SQLite."""
    trial = object.__new__(type(world))
    trial.__dict__.update(deepcopy({k: v for k, v in vars(world).items() if k != "log"}))
    trial.log = EventLog()
    for event in world.log.all():
        trial.log.append(event)
    return trial


def snapshot(world):
    state = {}
    for key, value in vars(world).items():
        if key in ("items", "npcs", "locations"):
            state[key] = {i: x.model_dump() for i, x in value.items()}
        elif key == "log":
            state[key] = [e.model_dump() for e in value.all()]
        elif key == "rng":
            state[key] = value.getstate()
        elif key == "clock":
            state[key] = vars(value).copy()
        else:
            state[key] = deepcopy(value)
    return state


def changed_paths(before, after, path=()):
    """Lists are atomic fields. Dictionary membership changes are changes too."""
    if isinstance(before, dict) and isinstance(after, dict):
        result = set()
        for key in before.keys() | after.keys():
            if key not in before or key not in after:
                result.add((*path, key))
            else:
                result |= changed_paths(before[key], after[key], (*path, key))
        return result
    return {path} if before != after else set()


def invariant_problem(before, after, actor, allowed):
    """Check everything, including fields no current effect knows how to change."""
    if set(before["items"]) != set(after["items"]):
        return "item count or set changed"
    if set(before["npcs"]) != set(after["npcs"]):
        return "person set changed"
    for npc_id, npc in before["npcs"].items():
        other = after["npcs"][npc_id]
        if npc["alive"] != other["alive"] or npc["held_by"] != other["held_by"]:
            return "alive or custody changed"
        if npc_id != actor and npc["location"] != other["location"]:
            return "someone other than the actor moved"
    if changed_paths(before, after) - allowed:
        return "changed a field outside the declared effects"
    return None


def dry_run(world, actor, definition, args):
    """No caller can commit until every step and the final state pass."""
    problem = shape_problem(world, definition)
    problem = problem or argument_problem(world, actor, definition, args)
    if problem:
        return problem, None, []
    trial = copy_world(world)
    records = []
    try:
        problem = needs_problem(trial, actor, definition["needs"], args)
        before, allowed = snapshot(world), set()
        for effect in definition["does"] if not problem else []:
            step_before = snapshot(trial)
            permitted = allowed_changes(trial, actor, effect, args)
            problem, record = run_step(trial, actor, effect, args)
            if problem:
                break
            problem = invariant_problem(step_before, snapshot(trial), actor, permitted)
            if problem:
                break
            allowed |= permitted
            records.append(record)
        if not problem:
            problem = invariant_problem(before, snapshot(trial), actor, allowed)
        if not problem:
            check_items(list(trial.items.values()), trial.locations, trial.npcs, trial.log)
        if problem:
            return problem, None, []
        # Only these verified fields are ever copied back to the real world.
        after = snapshot(trial)
        changes = {}
        for table, ident, field in sorted(changed_paths(before, after)):
            changes.setdefault(table, {}).setdefault(ident, {})[field] = after[table][ident][field]
        return None, changes, records
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        return f"invalid made action: {exc}", None, []
    finally:
        trial.log.db.close()
