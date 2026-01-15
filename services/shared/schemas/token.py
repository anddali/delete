"""
Token schemas for API token management.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import BaseSchema, PaginatedResponse


class TokenRateLimit(BaseModel):
    """Rate limit configuration for tokens."""
    
    per_minute: int = Field(default=100, ge=1, le=10000)
    per_day: int = Field(default=10000, ge=1, le=1000000)


class TokenScopes(BaseModel):
    """Token scopes configuration."""
    
    source_ids: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=lambda: ["read"])
    
    @field_validator("source_types")
    @classmethod
    def validate_source_types(cls, v: list[str]) -> list[str]:
        allowed_types = ["confluence", "slack", "file_upload"]
        for st in v:
            if st not in allowed_types:
                raise ValueError(f"Source type must be one of: {', '.join(allowed_types)}")
        return v
    
    @field_validator("operations")
    @classmethod
    def validate_operations(cls, v: list[str]) -> list[str]:
        allowed_ops = ["read", "write"]
        for op in v:
            if op not in allowed_ops:
                raise ValueError(f"Operation must be one of: {', '.join(allowed_ops)}")
        return v


class TokenCreate(BaseModel):
    """Token creation schema."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    type: str = Field(default="query", pattern="^(query|admin|service)$")
    scopes: TokenScopes = Field(default_factory=TokenScopes)
    rate_limit: TokenRateLimit = Field(default_factory=TokenRateLimit)
    expires_at: Optional[datetime] = None
    
    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed_types = ["query", "admin", "service"]
        if v not in allowed_types:
            raise ValueError(f"Type must be one of: {', '.join(allowed_types)}")
        return v


class TokenUpdate(BaseModel):
    """Token update schema."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    scopes: Optional[TokenScopes] = None
    rate_limit: Optional[TokenRateLimit] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


class TokenResponse(BaseSchema):
    """Token response schema (without full token)."""
    
    id: UUID
    name: str
    description: Optional[str] = None
    type: str
    token_preview: Optional[str] = None
    scopes: dict[str, Any]
    rate_limit: Optional[dict[str, int]] = None
    is_active: bool
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class TokenCreateResponse(TokenResponse):
    """Token creation response (includes full token once)."""
    
    token: str = Field(..., description="Full token - shown only once")


class TokenListResponse(PaginatedResponse[TokenResponse]):
    """Paginated token list response."""
    pass


class TokenUsageStats(BaseSchema):
    """Token usage statistics."""
    
    token_id: UUID
    total_requests: int
    requests_by_day: list[dict[str, Any]]
    top_queries: list[dict[str, Any]]
    error_rate: float
    avg_latency_ms: float
    cache_hit_rate: float
