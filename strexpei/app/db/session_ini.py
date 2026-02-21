from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from sqlalchemy.orm import sessionmaker
from ...config import Config
from sqlmodel import SQLModel

#create the engine connection
engine = create_async_engine(
    url=Config.DATABASE_URL,
    echo=True
)

#what we use to perform operations in postgres
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

#Set the session maker
Session = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with Session() as session:
        yield session