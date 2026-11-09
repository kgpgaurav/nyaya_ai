import json
import re
from datetime import date
from pathlib import Path

from sqlalchemy import func, literal, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .db import LegalSource

SOURCES_PATH = Path(__file__).parent / "data" / "sources.json"
TOKEN_RE = re.compile(r"[0-9A-Za-zऀ-ॿ]{3,}")
COLUMNS = (
    "id", "domains", "topics", "title", "citation", "summary_en", "summary_hi", "url", "locator",
    "priority", "in_force_from", "reviewed_on", "review_by", "caveat",
)


def load_cards(path: Path = SOURCES_PATH) -> list[dict]:
    cards = json.loads(path.read_text(encoding="utf-8"))
    for card in cards:
        for key in ("in_force_from", "reviewed_on", "review_by"):
            card[key] = date.fromisoformat(card[key]) if card.get(key) else None
    return cards


def card_dict(row: LegalSource) -> dict:
    return {c: getattr(row, c) for c in COLUMNS}


def serialisable(card: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in card.items()}


async def seed(session: AsyncSession, embedder=None, path: Path = SOURCES_PATH) -> int:
    cards = load_cards(path)
    for card in cards:
        values = {c: card.get(c) for c in COLUMNS}
        values["caveat"] = values["caveat"] or ""
        values["locator"] = values["locator"] or ""
        stmt = insert(LegalSource).values(**values)
        stmt = stmt.on_conflict_do_update(index_elements=["id"], set_={c: stmt.excluded[c] for c in COLUMNS if c != "id"})
        await session.execute(stmt)
    ids = [c["id"] for c in cards]
    await session.execute(text("DELETE FROM legal_sources WHERE NOT (id = ANY(:ids))"), {"ids": ids})
    await session.execute(
        text(
            "UPDATE legal_sources SET tsv = to_tsvector('simple', title || ' ' || citation || ' ' || "
            "summary_en || ' ' || summary_hi || ' ' || array_to_string(topics, ' ') || ' ' || caveat)"
        )
    )
    if embedder is not None:
        rows = (await session.execute(select(LegalSource))).scalars().all()
        vectors = await embedder.embed_documents([f"{r.title}. {r.citation}. {r.summary_en}" for r in rows])
        for row, vec in zip(rows, vectors):
            row.embedding = vec
    await session.commit()
    return len(cards)


def or_query(*parts: str) -> str:
    tokens = []
    for part in parts:
        for tok in TOKEN_RE.findall(part or ""):
            low = tok.lower()
            if low not in tokens:
                tokens.append(low)
    return " | ".join(tokens[:60])


async def retrieve(
    session: AsyncSession, domain: str, query: str, today: date, k: int = 6, embedder=None
) -> tuple[list[dict], int]:
    q = or_query(query)
    rank = func.ts_rank(LegalSource.tsv, func.to_tsquery("simple", q)) if q else literal(0.0)
    stmt = select(LegalSource, rank.label("rank")).where(LegalSource.domains.any(domain))
    if embedder is not None and q:
        vec = await embedder.embed_query(query)
        stmt = stmt.add_columns((1 - LegalSource.embedding.cosine_distance(vec)).label("sim"))
    rows = (await session.execute(stmt)).all()
    live, expired = [], 0
    for row in rows:
        src = row[0]
        if src.review_by < today or (src.in_force_from and src.in_force_from > today):
            expired += 1
            continue
        score = float(row.rank or 0)
        if embedder is not None and len(row) > 2 and row[2] is not None:
            score += float(row[2])
        live.append((src, score))
    core = sorted([x for x in live if x[0].priority <= 1], key=lambda x: x[0].priority)
    rest = sorted([x for x in live if x[0].priority > 1], key=lambda x: (-x[1], x[0].priority))
    picked = (core + rest)[:k]
    return [card_dict(src) for src, _ in picked], expired


async def get_cards(session: AsyncSession, ids: list[str], today: date) -> list[dict]:
    rows = (await session.execute(select(LegalSource).where(LegalSource.id.in_(ids)))).scalars().all()
    by_id = {r.id: card_dict(r) for r in rows if r.review_by >= today and not (r.in_force_from and r.in_force_from > today)}
    return [by_id[i] for i in ids if i in by_id]


async def all_cards(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(select(LegalSource).order_by(LegalSource.id))).scalars().all()
    return [serialisable(card_dict(r)) for r in rows]
