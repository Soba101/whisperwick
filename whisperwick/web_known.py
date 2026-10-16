"""Remember only Wren's filtered views. No world, feed, beliefs or secrets enter here."""

from copy import deepcopy


class Known:
    """Sightings belong to one player, so a new game starts with empty records."""

    def __init__(self):
        self.people: dict[str, dict] = {}
        self.bodies: dict[str, dict] = {}
        self.places: dict[str, dict] = {}
        self.items: dict[str, dict] = {}

    def update(self, view: dict) -> None:
        # Copy values so later views cannot rewrite an earlier sighting by aliasing it.
        place, clock = dict(view["place"]), view["clock"]
        self.places.setdefault(place["id"], place)
        for person in view["people"]:
            self.people[person["id"]] = {**person, "place": place, "clock": clock}
        for body in view["bodies"]:
            # A repeated view must not change when the body was first seen.
            self.bodies.setdefault(body["id"], {**body, "place": place, "clock": clock})
        for item in view["ground"]:
            self.items[item["id"]] = {**item, "carried": False, "place": place, "clock": clock}
        for item in view["carried"]:
            self.items[item["id"]] = {
                **self.items.get(item["id"], {}),
                **item,
                "carried": True,
                "carried_place": place,
                "carried_clock": clock,
            }
        carried = {item["id"] for item in view["carried"]}
        for item_id, item in self.items.items():
            if item["carried"] and item_id not in carried:
                # A gift leaves our hands, but does not become a ground sighting.
                item["carried"] = False

    def snapshot(self) -> dict:
        def ordered(records):
            # IDs break ties when two objects share a name.
            return sorted(records.values(), key=lambda row: (row["name"], row["id"]))

        # Places keep visit order; all other lists have a fixed name order.
        return deepcopy(
            {
                "people": ordered(self.people),
                "bodies": ordered(self.bodies),
                "places": list(self.places.values()),
                "items": ordered(self.items),
            }
        )
