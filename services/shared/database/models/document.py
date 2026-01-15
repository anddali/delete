"""
Document model for individual documents from sources.
"""

from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .source import Source
    from .document_chunk import DocumentChunk


class Document(Base, TimestampMixin):
    """Individual documents from sources."""
    
    __tablename__ = "documents"
    
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
    external_id: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    doc_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata",  # Keep column name as 'metadata' in DB
        JSONB,
        nullable=True,
        default=dict,
    )
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default="now()",
        nullable=False,
    )
    
    # Relationships
    source: Mapped["Source"] = relationship(
        "Source",
        back_populates="documents",
        lazy="selectin",
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.position",
    )
    
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_documents_source_external"),
        Index("idx_documents_source_id", "source_id"),
        Index("idx_documents_content_hash", "content_hash"),
        Index("idx_documents_updated_at", "updated_at", postgresql_ops={"updated_at": "DESC"}),
    )
    
    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title[:50]}...)>"
