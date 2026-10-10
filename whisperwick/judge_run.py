"""The after-run judge: ask small questions about a finished run and sum up the answers.

Each question is its own call, sampled without randomness (evenly spaced), so the same
run gets the same items. A model failure is counted, never raised. Nothing here touches
the world or a running village: it reads files and writes <db>.judge.json.
"""

from collections import defaultdict

from whisperwick import judge_questions as q
from whisperwick import story
from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.llm_client import LLMError

DEFAULT_LIMIT = 40  # items per question type
MAX_STORY_CHARS = 16000  # one day of story, cut to fit one llama-server slot (8192 tokens)


def pick(items: list, limit: int) -> list:
    """Up to `limit` items, evenly spaced from first to last. Same input, same pick."""
    if limit <= 0:
        return []
    if len(items) <= limit:
        return list(items)
    return [items[i * len(items) // limit] for i in range(limit)]


def ask(client, text: str, schema: dict, valid) -> dict:
    """One call. Returns {"inputs", "answer", "error"}; a bad or missing reply is an error."""
    item = {"inputs": text, "answer": None, "error": None}
    try:
        reply = client.chat(q.messages(text), schema)
        if not valid(reply):
            raise ValueError("reply does not fit the question")
        item["answer"] = reply
    except (LLMError, ValueError, KeyError, TypeError) as e:
        item["error"] = str(e)
    return item


def is_score(r) -> bool:
    return isinstance(r["score"], int) and 1 <= r["score"] <= 5


def is_yes_no(r) -> bool:
    return r["answer"] in ("yes", "no")


def is_misread(r) -> bool:
    return isinstance(r["misread"], bool)


def claim_items(events, names, client, limit) -> list[dict]:
    talks = [e for e in events if e.type == "talk" and e.data.get("claim")]
    out = []
    for e in pick(talks, limit):
        c = e.data["claim"]
        who, to = story.show(names, e.actor), story.show(names, e.data["to"])
        about = story.show(names, c["subject"])
        text = q.claim_text(who, to, e.data["message"], c["kind"], about)
        out.append({"event": e.id, **ask(client, text, q.YES_NO, is_yes_no)})
    return out


def cited(records: list[dict]) -> list[dict]:
    return [r for r in records if r.get("because")]


def support_items(records, names, client, limit) -> list[dict]:
    out = []
    for r in pick([r for r in cited(records) if r.get("suspect")], limit):
        text = q.support_text(story.show(names, r["suspect"]), r.get("of_what"),
                              [b["text"] for b in r["because"]])  # fmt: skip
        out.append({"npc": r["npc"], "tick": r["tick"], **ask(client, text, q.SCORE, is_score)})
    return out


def misread_items(records, client, limit) -> list[dict]:
    out = []
    for r in pick(cited(records), limit):
        text = q.misread_text(r["thoughts"], [b["text"] for b in r["because"]])
        out.append({"npc": r["npc"], "tick": r["tick"], **ask(client, text, q.MISREAD, is_misread)})
    return out


def coherence_items(events, sidecar, names, client) -> list[dict]:
    """One question per game day. Night thoughts are shown, the ground truth never is."""
    by_day = defaultdict(list)
    for e in events:
        by_day[e.tick // MINUTES_PER_DAY + 1].append(e)
    refl = {"reflections": sidecar.get("reflections", {})}
    out = []
    for day in sorted(by_day):
        day_story = story.format_story(by_day[day], names, refl)[:MAX_STORY_CHARS]
        out.append({"day": day, **ask(client, q.coherence_text(day_story), q.SCORE, is_score)})
    return out


def answered(items: list[dict]) -> list[dict]:
    return [i["answer"] for i in items if i["answer"] is not None]


def rate(hits: int, total: int) -> float | None:
    return hits / total if total else None


def summarise(sections: dict[str, list[dict]]) -> dict:
    claims = answered(sections["claims"])
    scores = [a["score"] for a in answered(sections["support"])]
    reads = answered(sections["misreads"])
    days = {i["day"]: i["answer"]["score"] for i in sections["coherence"] if i["answer"]}
    return {
        "claim_agreement": rate(sum(a["answer"] == "yes" for a in claims), len(claims)),
        "support_mean": sum(scores) / len(scores) if scores else None,
        "support_ok": rate(sum(s >= 3 for s in scores), len(scores)),
        "misread_rate": rate(sum(a["misread"] for a in reads), len(reads)),
        "coherence_by_day": days,
        # Failed calls are counted here so a weak judge shows up as a gap, not a crash.
        "failures": {k: sum(i["error"] is not None for i in v) for k, v in sections.items()},
        "asked": {k: len(v) for k, v in sections.items()},
    }


def judge(events, records, sidecar, names, client, limit=DEFAULT_LIMIT) -> dict:
    sections = {
        "claims": claim_items(events, names, client, limit),
        "support": support_items(records, names, client, limit),
        "misreads": misread_items(records, client, limit),
        "coherence": coherence_items(events, sidecar, names, client),
    }
    return {"limit": limit, "summary": summarise(sections), "items": sections}
