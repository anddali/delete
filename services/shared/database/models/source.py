"""
Source model for knowledge sources (Confluence, Slack, file uploads).
"""

from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .admin_user import AdminUser
    from .document import Document
    from .token_scope import TokenScope
    from .ingestion_job import IngestionJob


class Source(Base, TimestampMixin):
    """Knowledge sources (Confluence spaces, Slack channels, file collections)."""
    
    __tablename__ = "sources"
    
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
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    sync_frequency: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_sync_status: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    document_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
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
        back_populates="sources",
        lazy="selectin",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="source",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    token_scopes: Mapped[list["TokenScope"]] = relationship(
        "TokenScope",
        back_populates="source",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        "IngestionJob",
        back_populates="source",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        Index("idx_sources_type", "type"),
        Index("idx_sources_is_active", "is_active"),
        Index("idx_sources_created_by", "created_by"),
        Index("idx_sources_next_sync", "next_sync_at", postgresql_where="is_active = true"),
    )
    
    def get_chunking_config(self) -> dict[str, Any]:
        """Get chunking configuration from source config."""
        return self.config.get("chunking", {
            "chunk_size_chars": 1000,
            "respect_boundaries": True,
            "min_chunk_size_chars": 200,
        })
    
    def __repr__(self) -> str:
        return f"<Source(id={self.id}, name={self.name}, type={self.type})>"
