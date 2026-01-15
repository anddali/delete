"""
Query log model for analytics.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, Integer, String, Text, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .api_token import APIToken


class QueryLog(Base):
    """Log all queries for analytics (optional, high volume)."""
    
    __tablename__ = "query_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    token_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    query_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    query_embedding_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    results_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    cached: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    sliding_window: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    
    # Relationships
    token: Mapped[Optional["APIToken"]] = relationship(
        "APIToken",
        back_populates="query_logs",
        lazy="selectin",
    )
    
    __table_args__ = (
        Index("idx_query_logs_token_id", "token_id"),
        Index("idx_query_logs_created_at", "created_at", postgresql_ops={"created_at": "DESC"}),
        Index("idx_query_logs_cached", "cached"),
    )
    
    def __repr__(self) -> str:
        return f"<QueryLog(id={self.id}, latency_ms={self.latency_ms})>"
