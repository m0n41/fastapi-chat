from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.db.session import engine
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Не удалось подключиться к БД при старте приложения")
        await engine.dispose()
        raise
    
    logger.info("Приложение запущено")
    
    try:
        yield
    finally:
        await engine.dispose()
        logger.info("Завершение работы приложения")