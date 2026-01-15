"""
Redis cache service.
"""

import json
from typing import Any, Optional

import redis.asyncio as redis
import structlog

from app.config import settings

logger = structlog.get_logger()


class CacheService:
    """Redis cache service."""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
    
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self._client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            
            # Test connection
            await self._client.ping()
            logger.info("Redis cache connected")
        
        except Exception as e:
            logger.warning("Redis connection failed, caching disabled", error=str(e))
            self._client = None
    
    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
    
    async def get(self, key: str) -> Optional[dict]:
        """Get cached value."""
        if not self._client or not settings.CACHE_ENABLED:
            return None
        
        try:
            value = await self._client.get(key)
            if value:
                return json.loads(value)
            return None
        
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None
    
    async def set(
        self,
        key: str,
        value: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """Set cached value."""
        if not self._client or not settings.CACHE_ENABLED:
            return False
        
        try:
            ttl = ttl or settings.CACHE_TTL_SECONDS
            await self._client.set(key, json.dumps(value, default=str), ex=ttl)
            return True
        
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete cached value."""
        if not self._client:
            return False
        
        try:
            await self._client.delete(key)
            return True
        
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False
    
    async def clear_prefix(self, prefix: str) -> int:
        """Clear all keys with prefix."""
        if not self._client:
            return 0
        
        try:
            keys = await self._client.keys(f"{prefix}*")
            if keys:
                return await self._client.delete(*keys)
            return 0
        
        except Exception as e:
            logger.warning("Cache clear failed", prefix=prefix, error=str(e))
            return 0
    
    async def is_healthy(self) -> bool:
        """Check Redis health."""
        if not self._client:
            return False
        
        try:
            await self._client.ping()
            return True
        except Exception:
            return False


# Global cache service instance
cache_service = CacheService()
