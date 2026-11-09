import asyncio
import hashlib
from datetime import date

from app.corpus import or_query, retrieve, seed
from app.db import EMBED_DIM, make_engine, make_sessionmaker


class HashEmbedder:
    def _vec(self, text):
        v = [0.0] * EMBED_DIM
        for tok in text.lower().split():
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % EMBED_DIM] += 1.0
        n = sum(x * x for x in v) ** 0.5 or 1.0
        return [x / n for x in v]

    async def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    async def embed_query(self, text):
        return self._vec(text)


def run(coro_fn, url):
    async def go():
        engine = make_engine(url)
        try:
            async with make_sessionmaker(engine)() as s:
                return await coro_fn(s)
        finally:
            await engine.dispose()

    return asyncio.run(go())


def test_or_query_sanitises_input():
    q = or_query("deposit's & refund | DROP TABLE; मकान")
    assert "&" not in q.replace(" | ", "") and "मकान" in q and "drop" in q


def test_domain_filter_and_core_cards(database):
    cards, expired = run(lambda s: retrieve(s, "salary", "unpaid salary resigned", date(2026, 11, 9)), database)
    ids = [c["id"] for c in cards]
    assert ids[:2] == ["COW-COMMENCE", "COW-17"]
    assert all("salary" in c["domains"] for c in cards) and expired == 0


def test_expired_cards_are_counted_not_returned(database):
    cards, expired = run(lambda s: retrieve(s, "salary", "salary", date(2027, 1, 15)), database)
    assert not any(c["id"].startswith("COW") for c in cards)
    assert expired >= 4


def test_cards_not_yet_in_force_are_hidden(database):
    cards, _ = run(lambda s: retrieve(s, "salary", "salary", date(2025, 6, 1)), database)
    assert not any(c["id"].startswith("COW") for c in cards)


def test_vector_path_with_pgvector(database):
    emb = HashEmbedder()

    async def go(s):
        await seed(s, embedder=emb)
        return await retrieve(s, "refund", "grievance officer acknowledge complaint", date(2026, 11, 9), k=4, embedder=emb)

    cards, _ = run(go, database)
    assert "ECOM-4" in [c["id"] for c in cards]
