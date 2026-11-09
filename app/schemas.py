from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Domain = Literal["deposit", "refund", "salary", "notice", "other", "unknown"]
Intent = Literal["build_case", "explain", "draft", "practice", "notice", "chat"]
Risk = Literal["criminal", "police", "family", "court_deadline", "danger", "commercial", "fabrication", "injection"]
Mode = Literal["auto", "build_case", "explain", "draft", "practice", "notice"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Triage(Strict):
    domain: Domain = Field(description="Which problem type the overall conversation is about")
    intent: Intent = Field(description="What the person wants right now")
    risks: list[Risk] = Field(default_factory=list, description="Every risk flag that applies to the current message")
    language: Literal["en", "hi", "hinglish"] = Field(description="Language of the current message")


class ExtractedFact(Strict):
    field: str
    value: str = Field(description="Short value copied exactly from the quote")
    quote: str = Field(description="Exact span copied from the current message")
    correction: bool = Field(default=False, description="True only if the person explicitly corrects an earlier fact")


class ExtractedEvent(Strict):
    when: str = Field(description="Date or time words exactly as the person said them, or empty")
    what: str = Field(description="Short description of the event")
    quote: str = Field(description="Exact span copied from the current message")


class Extraction(Strict):
    facts: list[ExtractedFact] = Field(default_factory=list)
    events: list[ExtractedEvent] = Field(default_factory=list)


class Point(Strict):
    text: str
    sources: list[str] = Field(default_factory=list, description="IDs of source cards that support this point")


class Answer(Strict):
    points: list[Point] = Field(default_factory=list)


class PracticeTurn(Strict):
    opponent_reply: str
    coach_tip: str
    sources: list[str] = Field(default_factory=list)


NoticeKind = Literal[
    "court_summons", "police", "cheque_bounce", "legal_notice", "tax", "bank_recovery", "employer", "landlord", "other"
]


class NoticeReading(Strict):
    kind: NoticeKind
    sender: str = Field(description="Sender exactly as written in the notice, or empty")
    asks: str = Field(description="What the notice asks the person to do, in plain words")
    deadline_quote: str = Field(description="Exact words stating a deadline or date, or empty")
    summary: list[str] = Field(default_factory=list, description="Two to four plain-language sentences")


class DraftNarrative(Strict):
    paragraphs: list[str] = Field(default_factory=list)
