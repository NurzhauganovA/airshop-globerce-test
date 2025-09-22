# app/core/database.py

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from typing import Generator
import json

# Get the database URL from an environment variable.
# It's better to manage this outside the code for production.
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL")


def custom_json_serializer(obj):
    return json.dumps(obj, ensure_ascii=False)


# Create the SQLAlchemy engine.
# The `connect_args` are necessary for SQLite to function correctly.
# This argument is for SQLite only and is not needed for PostgreSQL.
engine = create_engine(SQLALCHEMY_DATABASE_URL, json_serializer=custom_json_serializer)

# Create a SessionLocal class. Each instance of this class will be
# a database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
