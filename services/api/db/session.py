"""Async SQLAlchemy session factory and database engine initialization."""

from __future__ import annotations

import os
import re
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from services.api.db.models import Base

DEFAULT_DB_URL = "sqlite+aiosqlite:///services/api/data/helm.db"


def normalize_db_url(url: str) -> str:
    """Normalize synchronous database URLs to async-compatible URLs."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def get_db_url() -> str:
    """Resolve database URL from environment or fallback to default."""
    raw_url = os.environ.get("DATABASE_URL") or os.environ.get("HELM_DATABASE_URL") or DEFAULT_DB_URL
    return normalize_db_url(raw_url)


def _ensure_sqlite_parent_dir(url: str) -> None:
    """Ensure directory exists if SQLite file path is specified."""
    if "sqlite" in url:
        match = re.search(r"sqlite(?:\+aiosqlite)?:///(.+)", url)
        if match:
            raw_path = match.group(1)
            if raw_path != ":memory:" and not raw_path.startswith("?"):
                path_obj = Path(raw_path)
                if path_obj.parent and not path_obj.parent.exists():
                    path_obj.parent.mkdir(parents=True, exist_ok=True)


def create_engine_and_sessionmaker(
    db_url: str | None = None,
    echo: bool = False,
    **engine_kwargs: Any,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create a new AsyncEngine and sessionmaker pair."""
    resolved_url = normalize_db_url(db_url) if db_url else get_db_url()
    _ensure_sqlite_parent_dir(resolved_url)

    engine = create_async_engine(
        resolved_url,
        echo=echo,
        future=True,
        **engine_kwargs,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return engine, session_factory


# Global engine and sessionmaker singleton instances
engine, AsyncSessionLocal = create_engine_and_sessionmaker()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency / context generator for acquiring an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db(target_engine: AsyncEngine | None = None) -> None:
    """Initialize database tables from SQLAlchemy metadata."""
    active_engine = target_engine or engine
    async with active_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db(target_engine: AsyncEngine | None = None) -> None:
    """Dispose the database engine and close active connections."""
    active_engine = target_engine or engine
    await active_engine.dispose()
