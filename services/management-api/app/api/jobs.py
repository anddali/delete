"""
Ingestion job management routes.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.services.auth import get_current_user, require_role, AdminUser
from shared.database.connection import get_db
from shared.database.models import IngestionJob, Source

logger = structlog.get_logger()

router = APIRouter()


class JobResponse(BaseModel):
    """Job response."""
    
    id: UUID
    source_id: UUID
    source_name: str
    type: str
    status: str
    progress: Optional[dict]
    result: Optional[dict]
    error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime


class JobDetailResponse(JobResponse):
    """Detailed job response."""
    
    source_type: str


class JobListResponse(BaseModel):
    """Paginated job list response."""
    
    items: List[JobResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=JobListResponse)
async def list_jobs(
    source_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List ingestion jobs with pagination."""
    # Build query
    query = (
        select(IngestionJob)
        .join(Source)
        .options(selectinload(IngestionJob.source))
    )
    
    if source_id:
        query = query.where(IngestionJob.source_id == source_id)
    
    if status_filter:
        query = query.where(IngestionJob.status == status_filter)
    
    # Count total
    count_query = select(func.count(IngestionJob.id))
    if source_id:
        count_query = count_query.where(IngestionJob.source_id == source_id)
    if status_filter:
        count_query = count_query.where(IngestionJob.status == status_filter)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.order_by(IngestionJob.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return JobListResponse(
        items=[
            JobResponse(
                id=j.id,
                source_id=j.source_id,
                source_name=j.source.name if j.source else "Unknown",
                type=j.type,
                status=j.status,
                progress=j.progress,
                result=j.result,
                error=j.error,
                started_at=j.started_at,
                completed_at=j.completed_at,
                created_at=j.created_at,
            )
            for j in jobs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: UUID,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get job details."""
    result = await db.execute(
        select(IngestionJob)
        .options(selectinload(IngestionJob.source))
        .where(IngestionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    return JobDetailResponse(
        id=job.id,
        source_id=job.source_id,
        source_name=job.source.name if job.source else "Unknown",
        source_type=job.source.type if job.source else "unknown",
        type=job.type,
        status=job.status,
        progress=job.progress,
        result=job.result,
        error=job.error,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
    )


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: UUID,
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running job."""
    result = await db.execute(
        select(IngestionJob).where(IngestionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    if job.status not in ["pending", "running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status}",
        )
    
    # Call ingestion service to cancel
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.INGESTION_SERVICE_URL}/ingest/cancel/{job_id}",
                timeout=30.0,
            )
            response.raise_for_status()
    
    except httpx.HTTPError as e:
        logger.error("Failed to cancel job", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion service unavailable",
        )
    
    return {"message": "Job cancelled"}


@router.get("/stats/summary")
async def get_job_stats(
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get job statistics summary."""
    # Count by status
    status_query = select(
        IngestionJob.status,
        func.count(IngestionJob.id)
    ).group_by(IngestionJob.status)
    
    result = await db.execute(status_query)
    status_counts = {row[0]: row[1] for row in result.fetchall()}
    
    # Recent failures
    failures_query = (
        select(IngestionJob)
        .options(selectinload(IngestionJob.source))
        .where(IngestionJob.status == "failed")
        .order_by(IngestionJob.completed_at.desc())
        .limit(5)
    )
    
    failures_result = await db.execute(failures_query)
    recent_failures = failures_result.scalars().all()
    
    return {
        "by_status": status_counts,
        "total": sum(status_counts.values()),
        "recent_failures": [
            {
                "id": str(j.id),
                "source_name": j.source.name if j.source else "Unknown",
                "error": j.error,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in recent_failures
        ],
    }
