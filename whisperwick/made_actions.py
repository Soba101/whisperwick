"""Register and use checked definitions. The model supplies intentions, never patches."""

from copy import deepcopy

from whisperwick.action_types import ActionResult, reject
from whisperwick.events import Event
from whisperwick.made_checks import dry_run
from whisperwick.made_shapes import shape_problem


def rebuild(events):
    """Definitions live in make events, so no second saved registry can drift."""
    actions = {}
    for event in events:
        if event.type == "make":
            definition = deepcopy(event.data["definition"])
            actions.setdefault(event.actor, {})[definition["name"]] = definition
    return actions


def apply_changes(world, changes):
    """Only engine-produced, verified patches reach this function."""
    for table, objects in changes.items():
        for ident, fields in objects.items():
            for field, value in fields.items():
                setattr(getattr(world, table)[ident], field, deepcopy(value))


def _finish(world, intent, data, changes, records):
    here = world.npcs[intent.actor].location
    witnesses = sorted({n for r in records for n in r["witnesses"]})
    data.update({"steps": records, "changes": changes})
    event = world.log.append(Event(
        tick=world.clock.tick, type=intent.action, actor=intent.actor,
        location=here, data=data, witnesses=witnesses,
    ))
    apply_changes(world, changes)
    return ActionResult(True, event=event)


def do_make(world, intent):
    if intent.actor == "player":
        return reject("made actions are villagers only")
    definition = {k: getattr(intent, k) for k in ("name", "params", "needs", "does")}
    problem = shape_problem(world, definition, new=True)
    if problem:
        return reject(problem)
    changes, records = {}, []
    if intent.use is not None:
        problem, changes, records = dry_run(world, intent.actor, definition, intent.use)
        if problem:
            return reject(problem)
    data = {"definition": deepcopy(definition)}
    if intent.use is not None:
        data["use"] = dict(intent.use)
    result = _finish(world, intent, data, changes, records)
    world.made_actions.setdefault(intent.actor, {})[intent.name] = deepcopy(definition)
    return result


def do_made(world, intent):
    if intent.actor == "player":
        return reject("made actions are villagers only")
    definition = world.made_actions[intent.actor][intent.action]
    args = {k: getattr(intent, k) for k in ("item", "person", "exit")
            if getattr(intent, k) is not None}
    problem, changes, records = dry_run(world, intent.actor, definition, args)
    if problem:
        return reject(problem)
    return _finish(world, intent, {"use": args}, changes, records)
