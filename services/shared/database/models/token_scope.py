"""
Token scope junction table for token access to specific sources.
"""

from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .api_token import APIToken
    from .source import Source


class TokenScope(Base):
    """Junction table for token access to specific sources (normalized)."""
    
    __tablename__ = "token_scopes"
    
    token_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_tokens.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    
    # Relationships
    token: Mapped["APIToken"] = relationship(
        "APIToken",
        back_populates="token_scopes",
        lazy="selectin",
    )
    source: Mapped["Source"] = relationship(
        "Source",
        back_populates="token_scopes",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return f"<TokenScope(token_id={self.token_id}, source_id={self.source_id})>"
