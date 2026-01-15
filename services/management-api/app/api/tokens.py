"""
API token management routes.
"""

import secrets
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.services.auth import get_current_user, require_role, AdminUser
from shared.database.connection import get_db
from shared.database.models import APIToken, TokenScope, Source, AuditLog
from shared.utils.security import generate_api_key, hash_token

logger = structlog.get_logger()

router = APIRouter()


class TokenCreate(BaseModel):
    """Create token request."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_ids: Optional[List[UUID]] = Field(
        default=None,
        description="List of source IDs this token can access. Empty = all sources.",
    )
    expires_in_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=365,
        description="Days until expiration. Null = never expires.",
    )
    rate_limit: Optional[int] = Field(
        default=100,
        ge=1,
        le=10000,
        description="Requests per minute",
    )


class TokenUpdate(BaseModel):
    """Update token request."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    source_ids: Optional[List[UUID]] = None
    rate_limit: Optional[int] = Field(None, ge=1, le=10000)
    is_active: Optional[bool] = None


class TokenResponse(BaseModel):
    """Token response (without the actual token)."""
    
    id: UUID
    name: str
    description: Optional[str]
    token_prefix: str
    is_active: bool
    rate_limit: Optional[int]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    created_at: datetime
    source_ids: List[UUID]


class TokenCreateResponse(TokenResponse):
    """Token creation response (includes the full token once)."""
    
    token: str = Field(
        ...,
        description="Full API token. Store this securely - it cannot be retrieved again.",
    )


@router.get("", response_model=List[TokenResponse])
async def list_tokens(
    is_active: Optional[bool] = None,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API tokens."""
    query = select(APIToken).options(selectinload(APIToken.scopes))
    
    if is_active is not None:
        query = query.where(APIToken.is_active == is_active)
    
    query = query.order_by(APIToken.name)
    
    result = await db.execute(query)
    tokens = result.scalars().all()
    
    return [
        TokenResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            token_prefix=t.token_prefix,
            is_active=t.is_active,
            rate_limit=t.rate_limit,
            expires_at=t.expires_at,
            last_used_at=t.last_used_at,
            created_at=t.created_at,
            source_ids=[s.source_id for s in t.scopes],
        )
        for t in tokens
    ]


@router.post("", response_model=TokenCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_token(
    request: TokenCreate,
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Create new API token."""
    # Validate source IDs if provided
    if request.source_ids:
        result = await db.execute(
            select(Source.id).where(Source.id.in_(request.source_ids))
        )
        existing = {row[0] for row in result.fetchall()}
        missing = set(request.source_ids) - existing
        
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source IDs: {missing}",
            )
    
    # Generate token
    raw_token = generate_api_key()
    token_hash = hash_token(raw_token)
    token_prefix = raw_token[:8]
    
    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
    
    # Create token
    token = APIToken(
        name=request.name,
        description=request.description,
        token_hash=token_hash,
        token_prefix=token_prefix,
        is_active=True,
        rate_limit=request.rate_limit,
        expires_at=expires_at,
    )
    db.add(token)
    await db.flush()  # Get token ID
    
    # Create scopes
    source_ids = request.source_ids or []
    for source_id in source_ids:
        scope = TokenScope(
            api_token_id=token.id,
            source_id=source_id,
        )
        db.add(scope)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="create",
        resource_type="api_token",
        resource_id=token.id,
        changes={"name": token.name, "source_count": len(source_ids)},
    )
    db.add(audit)
    
    await db.commit()
    
    logger.info("API token created", token_id=str(token.id), name=token.name)
    
    return TokenCreateResponse(
        id=token.id,
        name=token.name,
        description=token.description,
        token_prefix=token_prefix,
        token=raw_token,
        is_active=token.is_active,
        rate_limit=token.rate_limit,
        expires_at=token.expires_at,
        last_used_at=None,
        created_at=token.created_at,
        source_ids=source_ids,
    )


@router.get("/{token_id}", response_model=TokenResponse)
async def get_token(
    token_id: UUID,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get token details."""
    result = await db.execute(
        select(APIToken)
        .options(selectinload(APIToken.scopes))
        .where(APIToken.id == token_id)
    )
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
    
    return TokenResponse(
        id=token.id,
        name=token.name,
        description=token.description,
        token_prefix=token.token_prefix,
        is_active=token.is_active,
        rate_limit=token.rate_limit,
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        created_at=token.created_at,
        source_ids=[s.source_id for s in token.scopes],
    )


@router.put("/{token_id}", response_model=TokenResponse)
async def update_token(
    token_id: UUID,
    request: TokenUpdate,
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Update token."""
    result = await db.execute(
        select(APIToken)
        .options(selectinload(APIToken.scopes))
        .where(APIToken.id == token_id)
    )
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
    
    # Update fields
    if request.name is not None:
        token.name = request.name
    
    if request.description is not None:
        token.description = request.description
    
    if request.rate_limit is not None:
        token.rate_limit = request.rate_limit
    
    if request.is_active is not None:
        token.is_active = request.is_active
    
    # Update scopes
    if request.source_ids is not None:
        # Delete existing scopes
        await db.execute(
            delete(TokenScope).where(TokenScope.api_token_id == token.id)
        )
        
        # Create new scopes
        for source_id in request.source_ids:
            scope = TokenScope(
                api_token_id=token.id,
                source_id=source_id,
            )
            db.add(scope)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="update",
        resource_type="api_token",
        resource_id=token.id,
        changes=request.model_dump(exclude_none=True),
    )
    db.add(audit)
    
    await db.commit()
    
    # Refresh to get updated scopes
    result = await db.execute(
        select(APIToken)
        .options(selectinload(APIToken.scopes))
        .where(APIToken.id == token_id)
    )
    token = result.scalar_one()
    
    logger.info("API token updated", token_id=str(token_id))
    
    return TokenResponse(
        id=token.id,
        name=token.name,
        description=token.description,
        token_prefix=token.token_prefix,
        is_active=token.is_active,
        rate_limit=token.rate_limit,
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        created_at=token.created_at,
        source_ids=[s.source_id for s in token.scopes],
    )


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: UUID,
    current_user: AdminUser = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Revoke (delete) token."""
    result = await db.execute(
        select(APIToken).where(APIToken.id == token_id)
    )
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found",
        )
    
    # Delete scopes first
    await db.execute(
        delete(TokenScope).where(TokenScope.api_token_id == token_id)
    )
    
    # Delete token
    await db.delete(token)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="revoke",
        resource_type="api_token",
        resource_id=token_id,
        changes={"name": token.name},
    )
    db.add(audit)
    
    await db.commit()
    
    logger.info("API token revoked", token_id=str(token_id))
