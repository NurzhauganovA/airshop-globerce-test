# app/core/database.py

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Generator, AsyncGenerator, Callable
import json

# Get the database URL from an environment variable.
# It's better to manage this outside the code for production.
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL")
DB_POOL_SIZE = os.environ.get("DB_POOL_SIZE", 100)

# For the async engine, we need a URL with an async driver.
ASYNC_SQLALCHEMY_DATABASE_URL = None
if SQLALCHEMY_DATABASE_URL:
    # This creates an async-compatible URL, assuming you use PostgreSQL.
    ASYNC_SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")


def custom_json_serializer(obj):
    return json.dumps(obj, ensure_ascii=False)


# Create the SQLAlchemy engine.
# The `connect_args` are necessary for SQLite to function correctly.
# This argument is for SQLite only and is not needed for PostgreSQL.
engine = create_engine(SQLALCHEMY_DATABASE_URL, json_serializer=custom_json_serializer)


async_engine = create_async_engine(
    ASYNC_SQLALCHEMY_DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=max(1, DB_POOL_SIZE // 2),
    pool_use_lifo=True,
)

# Create a SessionLocal class. Each instance of this class will be
# a database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async_session: Callable[[], AsyncSession] = sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

# All your models will inherit from this Base class.
# This makes it easy for SQLAlchemy and Alembic to find and work with your tables.
Base = declarative_base()


def get_db() -> Generator:
    """
    Dependency to get a database session.
    This is used by FastAPI endpoints to handle sessions automatically.
    The session is created and then closed after the request is finished.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_db_session() -> AsyncGenerator:
    async with async_session() as session:
        yield session