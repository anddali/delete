"""
Health check service.
"""

from typing import Dict

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cache import cache_service

logger = structlog.get_logger()


async def check_all_health(db: AsyncSession) -> Dict[str, bool]:
    """Check health of all dependencies."""
    return {
        "database": await check_database(db),
        "redis": await check_redis(),
        "openai": await check_openai(),
    }


async def check_database(db: AsyncSession) -> bool:
    """Check database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("Database health check failed", error=str(e))
        return False


async def check_redis() -> bool:
    """Check Redis connectivity."""
    return await cache_service.is_healthy()


async def check_openai() -> bool:
    """Check OpenAI API accessibility."""
    from app.config import settings
    
    try:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Quick test with minimal tokens
        response = await client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input="test",
        )
        
        return len(response.data) > 0
    
    except Exception as e:
        logger.warning("OpenAI health check failed", error=str(e))
        return False
