"""Engine-owned physical pieces. They run only on the dry-run copy."""


def needs_problem(world, actor, needs, args):
    here = world.npcs[actor].location
    item = world.items.get(args.get("item"))
    for need in needs:
        if need == "holds_item" and item.holder != actor:
            return "you are not holding that item"
        if need == "item_here" and (item.location != here or not item.visible_to(actor)):
            return "item is not visible here"
        if need == "item_hidden_here" and (item.location != here or not item.hidden):
            return "item is not hidden here"
        if need == "person_here":
            person = world.npcs[args["person"]]
            if not person.alive or person.location != here:
                return "person is not here"
        if need.startswith("at_place:") and need.removeprefix("at_place:") != here:
            return "you are not at the required place"
    return None


def allowed_changes(world, actor, effect, args):
    """Exact object ids and fields permitted by this one declared piece."""
    if effect == "move_self_exit":
        return {("npcs", actor, "location")}
    ids = [args["item"]] if effect != "reveal_hidden_here" else [
        i.id for i in world.items.values()
        if i.hidden and i.location == world.npcs[actor].location
    ]
    fields = ("known_by",) if effect == "reveal_hidden_here" else (
        "holder", "location", "hidden", "known_by")
    return {("items", i, f) for i in ids for f in fields}


def run_step(world, actor, effect, args):
    """Return (problem, public record). No step can supply arbitrary state fields."""
    me = world.npcs[actor]
    here = me.location
    people = world.npcs_at(here)
    witnesses = [n for n in people if n != actor]
    record = {"effect": effect, "location": here, "witnesses": witnesses}
    # Match ordinary move/take/drop custody rules, even inside a longer sequence.
    if me.held_by is not None and effect != "reveal_hidden_here":
        return f"you are being held by {me.held_by}", None
    if effect == "move_self_exit":
        to = args["exit"]
        if to not in world.locations[here].links:
            return "exit is not reachable from here", None
        record.update({"from": here, "to": to})
        record["witnesses"] = sorted(set(people + world.npcs_at(to)) - {actor})
        me.location = to
    elif effect == "reveal_hidden_here":
        record["items"] = []
        for item in sorted(world.items.values(), key=lambda i: i.id):
            if item.hidden and item.location == here:
                item.known_by = sorted(set(item.known_by) | set(people))
                record["items"].append({"id": item.id, "name": item.name})
    else:
        item = world.items[args["item"]]
        if effect in ("put_item_here", "hide_item_here"):
            if item.holder != actor:
                return "you are not holding that item", None
            item.holder, item.location = None, here
            item.hidden = effect == "hide_item_here"
            item.known_by = [actor] if item.hidden else []
        elif effect == "take_item_here":
            if item.location != here or not item.visible_to(actor):
                return "item is not visible here", None
            item.holder, item.location = actor, None
            item.hidden, item.known_by = False, []
        if effect == "hide_item_here":
            # Bystanders do not learn the item's identity or hiding place.
            record["witnesses"] = []
        record.update({"item": item.id, "item_name": item.name})
    return None, record
