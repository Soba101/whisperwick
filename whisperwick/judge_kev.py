"""The Kev backend of the after-run judge: same items, same summary as judge_run.

Kev takes a text and several questions in one request. Answers are stored in the same
shape the chat judge uses (so judge_run.summarise works unchanged), plus the raw
probabilities. A failed request is counted per item, never raised.
"""

from collections import defaultdict

from whisperwick import judge_kev_questions as q
from whisperwick import story
from whisperwick.clock import MINUTES_PER_DAY
from whisperwick.judge_run import DEFAULT_LIMIT, cited, pick, summarise
from whisperwick.kev_client import MODEL
from whisperwick.llm_client import LLMError

# Kev's limit is 65,536 tokens, but on this GPU a day of 83,000 characters gave HTTP 500 and
# 48,000 took 50 s, while 32,000 took 3.5 s. So a long day is judged in parts of this size.
# In a full judging, 32,000-character parts still ran out of GPU memory once (oom_retries)
# and stalled Kev, so parts are 16,000 (1.7 s each).
MAX_STORY_CHARS = 16000


def p_yes(answer: dict) -> float:
    p = answer["noul"]
    if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 1:
        raise ValueError("noul answer is not a probability")
    return float(p)


def level(answer: dict) -> float:
    """Kev counts levels from 0; the chat judge uses 1-5. Same scale after +1."""
    s = answer["score"]
    if isinstance(s, bool) or not isinstance(s, (int, float)) or not 0 <= s <= 4:
        raise ValueError("score answer is out of range")
    return s + 1.0


def request(client, state: str, questions: dict) -> tuple[dict, str | None]:
    """One call. Returns (answers, error). A bad request gives no answers at all."""
    try:
        return client.ask(state, questions), None
    except (LLMError, ValueError, KeyError, TypeError) as e:
        return {}, str(e)


def parse(answers: dict, key: str, error: str | None, make) -> tuple[dict | None, str | None]:
    """Turn one question's answer into the stored shape, or say why it failed."""
    if error:
        return None, error
    try:
        return make(answers[key]), None
    except (KeyError, ValueError, TypeError) as e:
        return None, f"bad answer for {key}: {e}"


def as_claim(a: dict) -> dict:
    p = p_yes(a)
    return {"answer": "yes" if p >= 0.5 else "no", "p_yes": p}


def as_score(a: dict) -> dict:
    return {"score": level(a), "probabilities": a.get("probabilities")}


def as_misread(a: dict) -> dict:
    p = p_yes(a)
    return {"misread": p >= 0.5, "p_yes": p}


def item(base: dict, state: str, answer, error) -> dict:
    return {**base, "inputs": state, "answer": answer, "error": error}


def claim_items(events, names, client, limit) -> list[dict]:
    talks = [e for e in events if e.type == "talk" and e.data.get("claim")]
    out = []
    for e in pick(talks, limit):
        c = e.data["claim"]
        state = q.claim_state(story.show(names, e.actor), story.show(names, e.data["to"]),
                              e.data["message"])  # fmt: skip
        qs = {"claim": q.claim_question(c["kind"], story.show(names, c["subject"]))}
        answers, err = request(client, state, qs)
        out.append(item({"event": e.id}, state, *parse(answers, "claim", err, as_claim)))
    return out


def thought_items(records, names, client, limit) -> tuple[list[dict], list[dict]]:
    """Support and misread share one request per thought. Sampling is as for the chat judge."""
    sup = pick([r for r in cited(records) if r.get("suspect")], limit)
    mis = pick(cited(records), limit)
    keys = {(r["npc"], r["tick"]) for r in sup}
    mis_keys = {(r["npc"], r["tick"]) for r in mis}
    results = {}
    for r in sorted(sup + mis, key=lambda r: (r["tick"], r["npc"])):
        k = (r["npc"], r["tick"])
        if k in results:
            continue
        subject = story.show(names, r["suspect"]) if r.get("suspect") else None
        state = q.thought_state([b["text"] for b in r["because"]], r["thoughts"],
                                subject, r.get("of_what"))  # fmt: skip
        qs = {}
        if k in keys:
            qs["support"] = q.support_question()
        if k in mis_keys:
            qs["misread"] = q.misread_question()
        results[k] = (state, *request(client, state, qs))
    s_out, m_out = [], []
    for r in sup:
        state, answers, err = results[(r["npc"], r["tick"])]
        base = {"npc": r["npc"], "tick": r["tick"]}
        s_out.append(item(base, state, *parse(answers, "support", err, as_score)))
    for r in mis:
        state, answers, err = results[(r["npc"], r["tick"])]
        base = {"npc": r["npc"], "tick": r["tick"]}
        m_out.append(item(base, state, *parse(answers, "misread", err, as_misread)))
    return s_out, m_out


def coherence_items(events, sidecar, names, client) -> list[dict]:
    """One question per game day. Night thoughts are shown, the ground truth never is."""
    by_day = defaultdict(list)
    for e in events:
        by_day[e.tick // MINUTES_PER_DAY + 1].append(e)
    refl = {"reflections": sidecar.get("reflections", {})}
    out = []
    for day in sorted(by_day):
        text = story.format_story(by_day[day], names, refl)
        # Whole lines only, so no part starts or ends mid-sentence.
        for n, part in enumerate(parts(text, MAX_STORY_CHARS)):
            state = q.coherence_state(part)
            answers, err = request(client, state, {"coherence": q.coherence_question()})
            out.append(item({"day": day, "part": n}, state,
                            *parse(answers, "coherence", err, as_score)))  # fmt: skip
    return out


def parts(text: str, size: int) -> list[str]:
    """Split text at line breaks into pieces of at most size characters (a longer line is cut)."""
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        if cur and len(cur) + len(line) > size:
            out.append(cur)
            cur = ""
        cur += line[:size]
    return [*out, cur] if cur else out


def judge(events, records, sidecar, names, client, limit=DEFAULT_LIMIT) -> dict:
    support, misreads = thought_items(records, names, client, limit)
    sections = {
        "claims": claim_items(events, names, client, limit),
        "support": support,
        "misreads": misreads,
        "coherence": coherence_items(events, sidecar, names, client),
    }
    return {"limit": limit, "judge": MODEL, "summary": summarise(sections), "items": sections}
