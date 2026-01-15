"""
Database connection and session management utilities.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine as sa_create_async_engine,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool


def get_database_url(read_replica: bool = False) -> str:
    """Get database URL from environment."""
    if read_replica:
        url = os.getenv("DATABASE_READ_REPLICA_URL")
        if url:
            return url
    return os.getenv("DATABASE_URL", "postgresql+asyncpg://raguser:ragpassword@localhost:5432/ragdb")


def create_async_engine(
    database_url: Optional[str] = None,
    pool_size: int = 25,
    max_overflow: int = 10,
    echo: bool = False,
    pool_pre_ping: bool = True,
) -> AsyncEngine:
    """Create async SQLAlchemy engine with connection pooling."""
    url = database_url or get_database_url()
    
    # Use NullPool for testing or when explicitly needed
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "testing":
        return sa_create_async_engine(
            url,
            echo=echo,
            poolclass=NullPool,
        )
    
    return sa_create_async_engine(
        url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        pool_recycle=3600,  # Recycle connections after 1 hour
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


class DatabaseSessionManager:
    """Manager for database sessions with proper lifecycle management."""
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        pool_size: int = 25,
        max_overflow: int = 10,
        echo: bool = False,
    ):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._database_url = database_url
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._echo = echo
    
    def init(self, database_url: Optional[str] = None) -> None:
        """Initialize the database engine and session factory."""
        url = database_url or self._database_url or get_database_url()
        self._engine = create_async_engine(
            url,
            pool_size=self._pool_size,
            max_overflow=self._max_overflow,
            echo=self._echo,
        )
        self._session_factory = create_session_factory(self._engine)
    
    async def close(self) -> None:
        """Close the database engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session."""
        if self._session_factory is None:
            raise RuntimeError("DatabaseSessionManager is not initialized")
        
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[AsyncSession, None]:
        """Alias for session() for compatibility."""
        async with self.session() as session:
            yield session


# Global session manager instance
session_manager = DatabaseSessionManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting database sessions."""
    async with session_manager.session() as session:
        yield session


# Alias for compatibility
get_db = get_db_session
