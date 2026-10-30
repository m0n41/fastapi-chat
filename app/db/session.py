from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import Annotated
from app.config import settings

import os

engine = create_async_engine(settings.database_url)
get_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with get_session() as session:
        yield session
        
SessionDep = Annotated[AsyncSession, Depends(get_db)]

class Base(DeclarativeBase):
    pass