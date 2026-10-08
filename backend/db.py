"""Database access layer.

Switches between SQLite (local dev) and Postgres/Supabase (hosted) from a
single DATABASE_URL. Tables are created eagerly in `lifespan`.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./vidyapath.db",
)

# `check_same_thread` is required for SQLite's multi-threaded allowed mode.
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session() -> Generator:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create all tables. In a real project this is driven by models."""
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))
    # SQLite placeholder: models import here so their MetaData creates tables.
    # (Import side-effect keeps db.py free of a hard models import loop.)
    import backend.models  # noqa: F401


def run_migration(sql: str, params: dict | None = None) -> None:
    with get_session() as session:
        session.execute(text(sql), params or {})
        session.commit()
