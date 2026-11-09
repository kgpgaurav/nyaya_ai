import asyncio
import os
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config import Settings
from app.corpus import seed
from app.db import make_engine, make_sessionmaker
from app.main import create_app

ROOT = Path(__file__).resolve().parent.parent
TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://nyaya:nyaya@localhost:5432/nyaya_test")
TODAY = date(2026, 11, 9)
HEADERS = {"x-nyaya-client": "web"}


@pytest.fixture(scope="session", autouse=True)
def database():
    engine = create_engine(TEST_DB)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB)
    command.upgrade(cfg, "head")

    async def load():
        eng = make_engine(TEST_DB)
        async with make_sessionmaker(eng)() as s:
            await seed(s)
        await eng.dispose()

    asyncio.run(load())
    yield TEST_DB


def make_settings(**overrides) -> Settings:
    base = dict(
        database_url=TEST_DB,
        llm_provider="mock",
        stt_provider="mock",
        mock_fixtures=str(ROOT / "tests" / "mock_llm.json"),
        embedding_provider="none",
        max_calls_per_day=100000,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def make_client():
    clients = []

    def factory(today=TODAY, **overrides):
        app = create_app(make_settings(**overrides), today=lambda: today)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client):
    c = make_client()
    c.post("/api/case", headers=HEADERS)
    return c
