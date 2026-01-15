"""
Ingestion job model for tracking ingestion job history and status.
"""

from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .source import Source
    from .admin_user import AdminUser


class IngestionJob(Base):
    """Track ingestion job history and status."""
    
    __tablename__ = "ingestion_jobs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    progress: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
    )
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False,
    )
    
    # Relationships
    source: Mapped["Source"] = relationship(
        "Source",
        back_populates="ingestion_jobs",
        lazy="selectin",
    )
    created_by_user: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser",
        back_populates="jobs",
        lazy="selectin",
    )
    
    __table_args__ = (
        Index("idx_jobs_source_id", "source_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_type", "type"),
        Index("idx_jobs_created_at", "created_at", postgresql_ops={"created_at": "DESC"}),
        Index("idx_jobs_source_status_created", "source_id", "status", "created_at",
              postgresql_ops={"created_at": "DESC"}),
        Index("idx_jobs_running", "source_id", "created_at",
              postgresql_where="status = 'running'"),
    )
    
    def __repr__(self) -> str:
        return f"<IngestionJob(id={self.id}, type={self.type}, status={self.status})>"
