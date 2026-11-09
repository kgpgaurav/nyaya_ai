import re
from dataclasses import dataclass, field

from .provenance import norm

NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20", "thirty": "30",
    "forty-eight": "48", "forty eight": "48", "sixty": "60", "ninety": "90",
    "दो": "2", "तीन": "3", "चार": "4", "पांच": "5", "पाँच": "5", "छह": "6", "सात": "7", "दस": "10", "पंद्रह": "15", "तीस": "30",
    "एक": "1",
}
ORDINALS = {"first": "1st", "second": "2nd", "third": "3rd", "seventh": "7th", "tenth": "10th", "सातवें": "7th", "दूसरे": "2nd"}

UNIT_CANON = {
    "working day": "workday", "working days": "workday", "कार्य दिवस": "workday", "कार्य दिवसों": "workday",
    "day": "day", "days": "day", "दिन": "day",
    "hour": "hour", "hours": "hour", "घंटे": "hour", "घंटों": "hour",
    "week": "week", "weeks": "week", "सप्ताह": "week",
    "month": "month", "months": "month", "महीने": "month", "महीनों": "month",
    "year": "year", "years": "year", "साल": "year", "वर्ष": "year",
}

_NUM = r"(\d+|" + "|".join(sorted(map(re.escape, NUMBER_WORDS), key=len, reverse=True)) + r")"
_UNIT = r"(" + "|".join(sorted(map(re.escape, UNIT_CANON), key=len, reverse=True)) + r")"
PERIOD_RE = re.compile(_NUM + r"[\s-]*" + _UNIT + r"(?![\wऀ-ॿ])", re.I)
ORDINAL_RE = re.compile(r"\b(\d+(?:st|nd|rd|th)|" + "|".join(ORDINALS) + r")\s+(?:working\s+)?day", re.I)
MONEY_RE = re.compile(
    r"(?:rs\.?|₹|inr|rupees?)\s*([\d,]+(?:\.\d+)?)\s*(lakh|crore|लाख|करोड़)?"
    r"|([\d,]+(?:\.\d+)?)\s*(lakh|crore|लाख|करोड़|रुपये|rupees)",
    re.I,
)
SECTION_RE = re.compile(r"\b(?:sections?|secs?\.?|s\.|rules?|articles?|clauses?)\s*(\d+[A-Z]?)((?:\(\w+\))*)", re.I)
SECTION_HI_RE = re.compile(r"(?:धारा|नियम|अनुच्छेद)\s*(\d+[A-Z]?)")
ACT_RE = re.compile(
    r"\b((?:[A-Z][\w\-()]*\s+(?:(?:of|the|and|for|on|in|to)\s+)?){0,8}(?:Act|Code|Rules|Sanhita|Regulations))(?:,?\s*(\d{4}))?"
)
CODE_ON_RE = re.compile(r"\b(Code on [A-Z][\w]*(?:\s+[A-Z][\w]*)*)")
HINDI_ACTS = {
    "वेतन संहिता": "code on wages",
    "मजदूरी संहिता": "code on wages",
    "उपभोक्ता संरक्षण अधिनियम": "consumer protection act",
    "भारतीय संविदा अधिनियम": "indian contract act",
    "अनुबंध अधिनियम": "indian contract act",
    "परक्राम्य लिखत अधिनियम": "negotiable instruments act",
    "किरायेदारी अधिनियम": "model tenancy act",
    "विधिक सेवा प्राधिकरण अधिनियम": "legal services authorities act",
    "भारतीय नागरिक सुरक्षा संहिता": "bharatiya nagarik suraksha sanhita",
    "भारतीय न्याय संहिता": "bharatiya nyaya sanhita",
    "भारतीय दंड संहिता": "indian penal code",
    "वेतन भुगतान अधिनियम": "payment of wages act",
    "न्यूनतम वेतन अधिनियम": "minimum wages act",
    "सीमा अधिनियम": "limitation act",
}
CASE_LAW_RE = re.compile(
    r"\b[A-Z][\w.&]*(?:\s+[A-Z][\w.&]*)*\s+(?:v\.|vs\.?|versus)\s+[A-Z]|\bAIR\s+\d{4}\b|\bSCC\b|\b\d{4}\s+INSC\b|\bSCR\b",
)
PHONE_RE = re.compile(r"\b\d{4}[-\s]?\d{2,3}[-\s]?\d{3,4}\b|\b\d{5,}\b")
URL_RE = re.compile(r"https?://\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:gov\.in|nic\.in|com|org|in)\b", re.I)
NORMATIVE_RE = re.compile(
    r"\b(must|shall|entitled|right to|legally|by law|the law|illegal|unlawful|liable|obliged|required to|cannot refuse)\b"
    r"|(अधिकार|कानून|अवैध|बाध्य|ज़रूरी है|करना होगा|देना होगा)",
    re.I,
)
GENERIC_ACT_WORDS = {"act", "code", "rules", "the act", "the code", "the rules", "this act", "regulations"}


def _canon_num(token: str) -> str:
    token = token.lower().replace(",", "")
    return NUMBER_WORDS.get(token, token)


def periods(text: str) -> set[str]:
    out = {f"{_canon_num(n)} {UNIT_CANON[u.lower()]}" for n, u in PERIOD_RE.findall(text)}
    for o in ORDINAL_RE.findall(text):
        out.add(ORDINALS.get(o.lower(), o.lower()) + " dayofmonth")
    return out


def money(text: str) -> set[str]:
    out = set()
    for a, unit_a, b, unit_b in MONEY_RE.findall(text):
        amount = (a or b).replace(",", "").rstrip(".")
        unit = (unit_a or unit_b or "").lower()
        unit = {"लाख": "lakh", "करोड़": "crore", "रुपये": "", "rupees": ""}.get(unit, unit)
        if amount:
            out.add(f"{float(amount):g} {unit}".strip())
    return out


def section_numbers(text: str) -> set[str]:
    return {m[0].upper() for m in SECTION_RE.findall(text)} | {m.upper() for m in SECTION_HI_RE.findall(text)}


def act_names(text: str) -> set[str]:
    names = set()
    for name, _year in ACT_RE.findall(text):
        cleaned = re.sub(r"^(?:The|Under|Per|As|By|In)\s+", "", name.strip()).lower()
        if cleaned and cleaned not in GENERIC_ACT_WORDS and len(cleaned.split()) > 1:
            names.add(cleaned)
    for name in CODE_ON_RE.findall(text):
        names.add(name.lower())
    for hindi, english in HINDI_ACTS.items():
        if hindi in text:
            names.add(english)
    return names


def phones(text: str) -> set[str]:
    return {re.sub(r"\D", "", p) for p in PHONE_RE.findall(text)}


def urls(text: str) -> set[str]:
    return {u.lower().rstrip(".,)").removeprefix("https://").removeprefix("http://").removeprefix("www.") for u in URL_RE.findall(text)}


def card_text(card: dict) -> str:
    return " ".join(
        str(card.get(k) or "") for k in ("title", "citation", "summary_en", "summary_hi", "locator", "url", "caveat")
    )


@dataclass
class Evidence:
    text: str
    sections: set = field(default_factory=set)
    acts: str = ""
    periods: set = field(default_factory=set)
    money: set = field(default_factory=set)
    phones: set = field(default_factory=set)
    urls: str = ""

    @classmethod
    def build(cls, cards: list[dict], facts: dict) -> "Evidence":
        cards_blob = " ".join(card_text(c) for c in cards)
        facts_blob = " ".join(v["value"] for v in facts.values())
        blob = cards_blob + " " + facts_blob
        return cls(
            text=blob,
            sections=section_numbers(" ".join(c.get("citation", "") + " " + c.get("locator", "") for c in cards)),
            acts=norm(cards_blob).lower(),
            periods=periods(blob),
            money=money(blob),
            phones=phones(blob),
            urls=norm(blob).lower(),
        )


def problems_in(text: str, evidence: Evidence, cited: bool) -> list[str]:
    issues = []
    if CASE_LAW_RE.search(text):
        issues.append("mentions case law, which this assistant never cites")
    for sec in section_numbers(text):
        if sec not in evidence.sections:
            issues.append(f"section or rule {sec} is not in the cited sources")
    for act in act_names(text):
        if act.lower() not in evidence.acts:
            issues.append(f"'{act}' is not named in the cited sources")
    for p in periods(text) - evidence.periods:
        issues.append(f"time period '{p}' is not in the cited sources or your facts")
    for m in money(text) - evidence.money:
        issues.append(f"amount '{m}' is not in the cited sources or your facts")
    for ph in phones(text) - evidence.phones:
        issues.append(f"number {ph} is not in the cited sources")
    for u in urls(text):
        if u not in evidence.urls:
            issues.append(f"link {u} is not in the cited sources")
    if not cited and NORMATIVE_RE.search(text):
        issues.append("states a legal rule without citing a source")
    return issues


@dataclass
class Verdict:
    kept: list[dict]
    dropped: list[dict]

    @property
    def ok(self) -> bool:
        return bool(self.kept) and len(self.dropped) <= len(self.kept)


def verify_points(points: list[dict], retrieved: dict[str, dict], facts: dict) -> Verdict:
    kept, dropped = [], []
    for point in points:
        text = point.get("text", "").strip()
        if not text:
            continue
        known = [s for s in point.get("sources", []) if s in retrieved]
        unknown = [s for s in point.get("sources", []) if s not in retrieved]
        evidence = Evidence.build([retrieved[s] for s in known], facts)
        issues = [f"cites unknown source {s}" for s in unknown]
        issues += problems_in(text, evidence, cited=bool(known))
        if issues:
            dropped.append({"text": text, "sources": point.get("sources", []), "issues": issues})
        else:
            kept.append({"text": text, "sources": known})
    return Verdict(kept, dropped)


def verify_plain(text: str, allowed_cards: list[dict], facts: dict) -> list[str]:
    return problems_in(text, Evidence.build(allowed_cards, facts), cited=bool(allowed_cards))


ROLEPLAY_KINDS = ("case law", "section or rule", "is not named", "number ", "link ")


def roleplay_issues(text: str) -> list[str]:
    issues = problems_in(text, Evidence.build([], {}), cited=True)
    return [i for i in issues if any(k in i for k in ROLEPLAY_KINDS)]
