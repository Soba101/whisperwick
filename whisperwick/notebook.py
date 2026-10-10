"""A private notebook per villager: a few words about itself, one line per person.

Only the villager writes it (when it thinks). This code only stores, trims and shows it
back to its owner. It never writes a line itself. Agent side only: never world state.
"""

ME_MAX_CHARS = 300
PERSON_MAX_CHARS = 150
MAX_PEOPLE_PER_THOUGHT = 6


def trim(text, limit: int) -> str:
    """One line, whitespace flattened, cut to the limit (servers do not always enforce it)."""
    return " ".join(str(text or "").split())[:limit]


class Notebooks:
    def __init__(self):
        self.books: dict[str, dict] = {}

    def get(self, npc_id: str) -> dict:
        return self.books.setdefault(npc_id, {"me": None, "people": {}})

    def apply(self, npc_id: str, reply: dict, others: list[str]) -> None:
        """Take the villager's changes. Unknown people and odd shapes are ignored, not fatal."""
        book = self.get(npc_id)
        # null (or absent) keeps the note as it is. An empty string clears it.
        if isinstance(reply.get("notebook_me"), str):
            book["me"] = trim(reply["notebook_me"], ME_MAX_CHARS) or None
        entries = reply.get("notebook_people")
        for entry in (entries if isinstance(entries, list) else [])[:MAX_PEOPLE_PER_THOUGHT]:
            if not isinstance(entry, dict) or entry.get("person") not in others:
                continue
            line = trim(entry.get("line"), PERSON_MAX_CHARS)
            if line:
                book["people"][entry["person"]] = line  # replaces the old line
            else:
                book["people"].pop(entry["person"], None)  # empty removes it

    def lines(self, npc_id: str, world) -> list[str]:
        """Plain lines for the owner's prompt. Nothing at all when the notebook is empty."""
        book = self.books.get(npc_id)
        if not book or not (book["me"] or book["people"]):
            return []
        out = ["Your private notebook (only you can see it):"]
        if book["me"]:
            out.append(f"About you: {book['me']}")
        for person, line in sorted(book["people"].items()):
            out.append(f"- {world.npcs[person].name} ({person}): {line}")
        return out

    def to_dict(self) -> dict:
        books = sorted(self.books.items())
        return {n: {"me": b["me"], "people": dict(b["people"])} for n, b in books}
