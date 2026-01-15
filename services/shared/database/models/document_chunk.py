"""
Document chunk model with embeddings for vector search.
"""

from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from .base import Base

if TYPE_CHECKING:
    from .document import Document


class DocumentChunk(Base):
    """
    Chunked document content with embeddings (no overlap).
    
    Chunks are stored sequentially with position tracking to enable
    efficient sliding window retrieval at query time.
    """
    
    __tablename__ = "document_chunks"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(1536),  # OpenAI text-embedding-3-small dimensions
        nullable=True,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequential chunk position (0-indexed) for sliding window retrieval",
    )
    char_start: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Character offset where chunk starts in original document",
    )
    char_end: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Character offset where chunk ends in original document",
    )
    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Length of this chunk in characters",
    )
    chunk_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata",  # Keep column name as 'metadata' in DB
        JSONB,
        nullable=True,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    
    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
        lazy="selectin",
    )
    
    __table_args__ = (
        UniqueConstraint("document_id", "position", name="uq_chunks_document_position"),
        Index("idx_chunks_document_id", "document_id"),
        Index("idx_chunks_position", "document_id", "position"),
        Index("idx_chunks_doc_position_range", "document_id", "position",
              postgresql_where="position IS NOT NULL"),
        # HNSW index for vector search - created in migration
    )
    
    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, position={self.position}, chars={self.char_count})>"
