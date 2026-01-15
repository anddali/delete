"""
Common schemas used across the application.
"""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class PaginatedResponse(BaseSchema, Generic[T]):
    """Paginated response wrapper."""
    
    items: list[T]
    total: int
    page: int
    limit: int
    pages: int
    
    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        limit: int,
    ) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        pages = (total + limit - 1) // limit if limit > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )


class HealthResponse(BaseSchema):
    """Health check response."""
    
    status: str = "healthy"
    version: str = "1.0.0"
    database: bool = True
    redis: bool = True
    openai: Optional[bool] = None
    details: Optional[dict[str, Any]] = None


class ErrorResponse(BaseSchema):
    """Error response."""
    
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
    request_id: Optional[str] = None


class MessageResponse(BaseSchema):
    """Simple message response."""
    
    message: str
    success: bool = True


class TimestampMixin(BaseSchema):
    """Mixin for timestamp fields."""
    
    created_at: datetime
    updated_at: datetime
