from dataclasses import dataclass, field
from datetime import date
from typing import Any, TypedDict

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..llm import LLM, Recorder


class CaseState(TypedDict, total=False):
    case_id: str
    turn: int
    message: str
    requested_mode: str
    language_pref: str
    language: str
    domain: str
    intent: str
    risks: list[str]
    soft_risks: list[str]
    mode: str
    facts: dict
    events: list
    history: list
    practice_log: list
    notice: dict
    sources: list
    expired: int
    points: list
    dropped: list
    attempts: int
    retry: bool
    notes: list
    conflicts: list
    canned: str
    next_question: str
    reply: str
    blocks: dict
    citations: list
    draft: dict
    confirmed: bool


@dataclass
class Ctx:
    llm: LLM
    sessions: async_sessionmaker
    recorder: Recorder = field(default_factory=Recorder)
    today: date = field(default_factory=date.today)
    embedder: Any = None


PER_TURN_RESET = {
    "risks": [],
    "soft_risks": [],
    "sources": [],
    "expired": 0,
    "points": [],
    "dropped": [],
    "attempts": 0,
    "retry": False,
    "notes": [],
    "conflicts": [],
    "canned": "",
    "next_question": "",
    "reply": "",
    "blocks": {},
    "citations": [],
    "draft": {},
}
