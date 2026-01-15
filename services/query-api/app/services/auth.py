"""
API token authentication service.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.database.connection import session_manager
from shared.database.models import APIToken, TokenScope

logger = structlog.get_logger()


@dataclass
class TokenData:
    """Validated token data."""
    
    token_id: UUID
    name: str
    source_ids: Optional[List[UUID]]
    rate_limit: Optional[int]
    created_at: datetime


async def get_api_token(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> TokenData:
    """
    Validate API token from header.
    
    Returns token data if valid.
    Raises HTTPException if invalid.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "X-API-Key"},
        )
    
    # Hash the token to find in database
    token_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    
    async with session_manager.session() as db:
        # Find token
        result = await db.execute(
            select(APIToken)
            .options(selectinload(APIToken.token_scopes))
            .where(
                APIToken.token_hash == token_hash,
                APIToken.is_active == True,
            )
        )
        token = result.scalar_one_or_none()
        
        if not token:
            logger.warning("Invalid API token attempted")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        
        # Check expiration
        if token.expires_at and token.expires_at < datetime.utcnow():
            logger.warning("Expired API token used", token_id=str(token.id))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key expired",
            )
        
        # Update last used
        token.last_used_at = datetime.utcnow()
        await db.commit()
        
        # Get source IDs from scopes
        source_ids = None
        if token.token_scopes:
            source_ids = [scope.source_id for scope in token.token_scopes]
        
        return TokenData(
            token_id=token.id,
            name=token.name,
            source_ids=source_ids,
            rate_limit=token.rate_limit,
            created_at=token.created_at,
        )


async def validate_token(token: str) -> Optional[TokenData]:
    """
    Validate token without raising exception.
    
    Returns TokenData if valid, None otherwise.
    """
    try:
        return await get_api_token(x_api_key=token)
    except HTTPException:
        return None
