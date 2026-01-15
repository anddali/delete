"""
System settings model for system-wide configuration.
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SystemSetting(Base):
    """System-wide configuration."""
    
    __tablename__ = "system_settings"
    
    key: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )
    value: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<SystemSetting(key={self.key})>"


# Default settings values
DEFAULT_SETTINGS = {
    "embedding": {
        "model": "text-embedding-3-small",
        "dimensions": 1536,
    },
    "chunking": {
        "default_chunk_size_chars": 1000,
        "default_respect_boundaries": True,
        "default_min_chunk_size_chars": 200,
        "chunk_size_range": [500, 4000],
    },
    "search": {
        "default_top_k": 10,
        "max_top_k": 100,
        "min_similarity_score": 0.7,
        "default_sliding_window": 0,
        "max_sliding_window": 3,
    },
    "rate_limiting": {
        "default_per_minute": 100,
        "default_per_day": 10000,
    },
    "retention": {
        "audit_log_days": 90,
        "job_log_days": 30,
    },
}
