"""
Admin user model for authentication and authorization.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .source import Source
    from .api_token import APIToken
    from .ingestion_job import IngestionJob
    from .audit_log import AuditLog


class AdminUser(Base, TimestampMixin):
    """Admin users who can access the management interface."""
    
    __tablename__ = "admin_users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationships
    sources: Mapped[list["Source"]] = relationship(
        "Source",
        back_populates="created_by_user",
        lazy="selectin",
    )
    tokens: Mapped[list["APIToken"]] = relationship(
        "APIToken",
        back_populates="created_by_user",
        lazy="selectin",
    )
    jobs: Mapped[list["IngestionJob"]] = relationship(
        "IngestionJob",
        back_populates="created_by_user",
        lazy="selectin",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        lazy="selectin",
    )
    
    __table_args__ = (
        Index("idx_admin_users_role", "role"),
        Index("idx_admin_users_is_active", "is_active"),
    )
    
    def __repr__(self) -> str:
        return f"<AdminUser(id={self.id}, email={self.email}, role={self.role})>"
