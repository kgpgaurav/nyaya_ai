import asyncio

from .config import get_settings
from .corpus import seed
from .db import make_engine, make_sessionmaker
from .embeddings import build_embedder


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    sessions = make_sessionmaker(engine)
    async with sessions() as session:
        count = await seed(session, embedder=build_embedder(settings))
    await engine.dispose()
    print(f"Loaded {count} source cards")


if __name__ == "__main__":
    asyncio.run(main())
