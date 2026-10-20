"""Viewer-specific words for resolved steps. Hidden details never leave their audience."""


def step_lines(event, names, viewer=None):
    who = names.get(event.actor, event.actor)
    lines = []
    for step in event.data.get("steps", []):
        if viewer is not None and viewer != event.actor and viewer not in step["witnesses"]:
            continue
        effect = step["effect"]
        item = step.get("item_name", "item")
        if effect == "move_self_exit":
            src, dst = (names.get(step[k], step[k]) for k in ("from", "to"))
            words = f"walks {src} -> {dst}"
        elif effect == "reveal_hidden_here":
            items = ", ".join(i["name"] for i in step["items"])
            words = f"reveals {items}" if items else "looks for hidden items"
        else:
            verb = {"put_item_here": "puts down", "hide_item_here": "hides",
                    "take_item_here": "takes"}[effect]
            words = f"{verb} the {item}"
        lines.append(f"{who} {words}")
    if not lines and (viewer is None or viewer == event.actor) and event.type == "make":
        lines.append(f"{who} makes the action {event.data['definition']['name']}")
    return lines
