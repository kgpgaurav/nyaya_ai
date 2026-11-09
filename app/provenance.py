import unicodedata

from .domains import field_names
from .schemas import Extraction

MAX_VALUE = 400


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return " ".join(text.replace("’", "'").replace("“", '"').replace("”", '"').split())


def grounded(value: str, quote: str, message: str) -> bool:
    v, q, m = norm(value), norm(quote), norm(message)
    if not v or not q or len(v) > MAX_VALUE:
        return False
    return q.casefold() in m.casefold() and v.casefold() in q.casefold()


def merge_extraction(domain: str, extraction: Extraction, message: str, facts: dict, events: list, turn: int):
    allowed = set(field_names(domain))
    facts = {k: dict(v) for k, v in facts.items()}
    events = list(events)
    dropped = 0
    conflicts = []
    for fact in extraction.facts:
        if fact.field not in allowed or not grounded(fact.value, fact.quote, message):
            dropped += 1
            continue
        value, quote = norm(fact.value), norm(fact.quote)
        existing = facts.get(fact.field)
        if existing and existing["value"].casefold() != value.casefold() and not fact.correction:
            conflicts.append({"field": fact.field, "old": existing["value"], "new": value})
            continue
        facts[fact.field] = {"value": value, "quote": quote, "turn": turn, "confirmed": False}
    for event in extraction.events:
        if not grounded(event.quote, event.quote, message) or not event.what.strip() or len(event.what) > 200:
            dropped += 1
            continue
        if event.when and norm(event.when).casefold() not in norm(event.quote).casefold():
            dropped += 1
            continue
        events.append({"when": norm(event.when), "what": norm(event.what), "quote": norm(event.quote), "turn": turn})
    return facts, events, dropped, conflicts
