import os

import pytest
import pytest_asyncio
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from app.db.session import Base

test_database_url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(".env").get(
    "TEST_DATABASE_URL"
)
if not test_database_url:
    raise RuntimeError("Set TEST_DATABASE_URL in the environment or .env before running tests")

test_database = make_url(test_database_url)
if not test_database.database or not test_database.database.endswith("_test"):
    raise ValueError("TEST_DATABASE_URL must point to a database whose name ends with '_test'")

TEST_ASYNC_DB_URL = test_database.set(drivername="postgresql+asyncpg")
TEST_SYNC_DB_URL = test_database.set(drivername="postgresql+psycopg")

test_async_engine = create_async_engine(
    TEST_ASYNC_DB_URL,
    poolclass=NullPool,
)

test_get_session = async_sessionmaker(
    test_async_engine,
    expire_on_commit=False,
)


@pytest.fixture(autouse=True)
def use_test_database(monkeypatch):
    from app.db import lifecycle, session
    from app.messages import websocket

    monkeypatch.setattr(session, "engine", test_async_engine)
    monkeypatch.setattr(session, "get_session", test_get_session)
    monkeypatch.setattr(lifecycle, "engine", test_async_engine)
    monkeypatch.setattr(websocket, "get_session", test_get_session)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    with create_engine(TEST_SYNC_DB_URL).begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    async with test_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await test_async_engine.dispose()

    with create_engine(TEST_SYNC_DB_URL).begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture
def db_session():
    """Синхронная сессия для проверки данных в тестах."""
    engine = create_engine(TEST_SYNC_DB_URL)
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
        engine.dispose()