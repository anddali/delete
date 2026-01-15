"""
API Token model for query API authentication.
"""

from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .admin_user import AdminUser
    from .token_scope import TokenScope
    from .query_log import QueryLog


class APIToken(Base, TimestampMixin):
    """API tokens for accessing the query API."""
    
    __tablename__ = "api_tokens"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )
    token_preview: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
    )
    scopes: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    rate_limit: Mapped[Optional[dict[str, int]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    usage_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Relationships
    created_by_user: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        back_populates="tokens",
        lazy="selectin",
    )
    token_scopes: Mapped[list["TokenScope"]] = relationship(
        "TokenScope",
        back_populates="token",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    query_logs: Mapped[list["QueryLog"]] = relationship(
        "QueryLog",
        back_populates="token",
        lazy="selectin",
    )
    
    __table_args__ = (
        Index("idx_tokens_token_hash", "token_hash"),
        Index("idx_tokens_type", "type"),
        Index("idx_tokens_is_active", "is_active"),
        Index("idx_tokens_expires_at", "expires_at", postgresql_where="expires_at IS NOT NULL"),
        Index("idx_tokens_scopes", "scopes", postgresql_using="gin"),
    )
    
    def get_rate_limits(self) -> dict[str, int]:
        """Get rate limits with defaults."""
        return self.rate_limit or {
            "per_minute": 100,
            "per_day": 10000,
        }
    
    def get_source_ids(self) -> list[str]:
        """Get allowed source IDs from scopes."""
        return self.scopes.get("source_ids", [])
    
    def __repr__(self) -> str:
        return f"<APIToken(id={self.id}, name={self.name}, type={self.type})>"
