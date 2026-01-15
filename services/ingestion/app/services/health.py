"""
Health check service
"""

import asyncio
from typing import Any

import redis.asyncio as redis
import structlog
from sqlalchemy import text

from app.config import settings
from shared.database.connection import session_manager

logger = structlog.get_logger()


async def check_database() -> bool:
    """Check database connectivity."""
    try:
        async with session_manager.session() as db:
            await db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False


async def check_redis() -> bool:
    """Check Redis connectivity."""
    try:
        client = redis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.aclose()
        return True
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        return False


async def check_openai() -> bool:
    """Check OpenAI API availability."""
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                timeout=5.0,
            )
            return response.status_code == 200
    except Exception as e:
        logger.error("OpenAI health check failed", error=str(e))
        return False


async def check_health() -> dict[str, Any]:
    """Run all health checks."""
    db_healthy, redis_healthy = await asyncio.gather(
        check_database(),
        check_redis(),
    )
    
    # OpenAI check is optional - don't block on it
    openai_healthy = None
    if settings.OPENAI_API_KEY:
        try:
            openai_healthy = await asyncio.wait_for(check_openai(), timeout=5.0)
        except asyncio.TimeoutError:
            openai_healthy = False
    
    all_healthy = db_healthy and redis_healthy
    
    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "version": "1.0.0",
        "database": db_healthy,
        "redis": redis_healthy,
        "openai": openai_healthy,
        "details": {
            "environment": settings.ENVIRONMENT,
        },
    }
