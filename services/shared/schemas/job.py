"""
Job schemas for ingestion job management.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .common import BaseSchema, PaginatedResponse


class JobProgress(BaseModel):
    """Job progress tracking."""
    
    processed: int = 0
    total: Optional[int] = None
    current_step: Optional[str] = None
    percentage: Optional[float] = None


class JobResult(BaseModel):
    """Job result summary."""
    
    documents_added: int = 0
    documents_updated: int = 0
    documents_deleted: int = 0
    chunks_created: int = 0
    embeddings_generated: int = 0
    errors: list[str] = Field(default_factory=list)


class TriggerIngestionRequest(BaseModel):
    """Request to trigger ingestion job."""
    
    source_id: UUID
    full_sync: bool = Field(
        default=False,
        description="If true, perform full sync instead of incremental",
    )


class JobResponse(BaseSchema):
    """Job response schema."""
    
    id: UUID
    source_id: UUID
    source_name: Optional[str] = None
    type: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Optional[JobProgress] = None
    result: Optional[JobResult] = None
    error: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class JobListResponse(PaginatedResponse[JobResponse]):
    """Paginated job list response."""
    pass


class JobStats(BaseSchema):
    """Job statistics summary."""
    
    total_jobs: int
    by_status: dict[str, int]
    by_type: dict[str, int]
    average_duration_seconds: float
    success_rate: float
    jobs_last_24h: int
    jobs_last_7d: int
