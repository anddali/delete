"""
Source schemas.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import BaseSchema, PaginatedResponse


class ChunkingConfig(BaseModel):
    """Chunking configuration for a source."""
    
    chunk_size_chars: int = Field(
        default=1000,
        ge=500,
        le=4000,
        description="Target size for each chunk in characters",
    )
    respect_boundaries: bool = Field(
        default=True,
        description="Try to break at natural boundaries (sentences, paragraphs)",
    )
    min_chunk_size_chars: int = Field(
        default=200,
        ge=50,
        le=500,
        description="Minimum chunk size to keep",
    )


class ConfluenceCredentials(BaseModel):
    """Confluence credentials."""
    
    email: str
    api_token: str


class ConfluenceConfig(BaseModel):
    """Confluence source configuration."""
    
    base_url: str = Field(..., description="Confluence base URL")
    space_keys: list[str] = Field(..., min_length=1, description="Space keys to sync")
    credentials: ConfluenceCredentials
    options: dict[str, Any] = Field(
        default_factory=lambda: {
            "include_attachments": True,
            "include_archived": False,
            "max_page_size": 1000,
        }
    )
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)


class SlackCredentials(BaseModel):
    """Slack credentials."""
    
    bot_token: str


class SlackConfig(BaseModel):
    """Slack source configuration."""
    
    workspace_id: str
    channel_ids: list[str] = Field(..., min_length=1)
    credentials: SlackCredentials
    options: dict[str, Any] = Field(
        default_factory=lambda: {
            "include_threads": True,
            "include_files": True,
            "min_message_length": 10,
            "max_age_days": 365,
        }
    )
    chunking: ChunkingConfig = Field(
        default_factory=lambda: ChunkingConfig(
            chunk_size_chars=800,
            min_chunk_size_chars=150,
        )
    )


class FileUploadStorageConfig(BaseModel):
    """File upload storage configuration."""
    
    type: str = "s3"
    bucket: str
    prefix: str = "uploads/"
    region: str = "us-east-1"


class FileUploadConfig(BaseModel):
    """File upload source configuration."""
    
    storage: FileUploadStorageConfig
    processing: dict[str, Any] = Field(
        default_factory=lambda: {
            "max_file_size_mb": 100,
            "allowed_extensions": [".pdf", ".docx", ".txt", ".md"],
            "ocr_enabled": False,
        }
    )
    chunking: ChunkingConfig = Field(
        default_factory=lambda: ChunkingConfig(
            chunk_size_chars=1200,
            min_chunk_size_chars=250,
        )
    )


class SourceCreate(BaseModel):
    """Source creation schema."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    type: str = Field(..., pattern="^(confluence|slack|file_upload)$")
    config: dict[str, Any]
    sync_frequency: Optional[str] = Field(
        default="0 */6 * * *",
        description="Cron expression for sync schedule",
    )
    
    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed_types = ["confluence", "slack", "file_upload"]
        if v not in allowed_types:
            raise ValueError(f"Type must be one of: {', '.join(allowed_types)}")
        return v


class SourceUpdate(BaseModel):
    """Source update schema."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    sync_frequency: Optional[str] = None
    is_active: Optional[bool] = None


class SourceResponse(BaseSchema):
    """Source response schema."""
    
    id: UUID
    name: str
    description: Optional[str] = None
    type: str
    config: dict[str, Any]
    is_active: bool
    sync_frequency: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    next_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    document_count: int = 0
    chunk_count: int = 0
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    
    def mask_credentials(self) -> "SourceResponse":
        """Return a copy with masked credentials."""
        config = self.config.copy()
        if "credentials" in config:
            config["credentials"] = {
                k: "***" for k in config["credentials"]
            }
        return self.model_copy(update={"config": config})


class SourceListResponse(PaginatedResponse[SourceResponse]):
    """Paginated source list response."""
    pass


class SourceStats(BaseSchema):
    """Source statistics."""
    
    source_id: UUID
    document_count: int
    chunk_count: int
    total_content_size: int
    last_sync_at: Optional[datetime] = None
    avg_document_size: float
    sync_history: list[dict[str, Any]] = []
    error_count: int = 0
