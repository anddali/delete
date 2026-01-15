"""
API routes for Ingestion Service
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.workers.celery_app import celery_app
from app.workers.tasks import ingest_source, process_uploaded_document
from shared.database.connection import get_db_session
from shared.database.models import IngestionJob, Source, Document
from shared.schemas import TriggerIngestionRequest, JobResponse, JobProgress, JobResult

logger = structlog.get_logger()

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/trigger", response_model=JobResponse)
async def trigger_ingestion(
    request: TriggerIngestionRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Trigger ingestion for a source."""
    # Verify source exists
    result = await db.execute(
        select(Source).where(Source.id == request.source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source not found: {request.source_id}",
        )
    
    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source is not active",
        )
    
    # Create job record
    job = IngestionJob(
        source_id=request.source_id,
        type="full_sync" if request.full_sync else "incremental",
        status="pending",
        progress={"processed": 0, "total": None, "current_step": "queued"},
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Queue the task
    task = ingest_source.delay(str(job.id), str(request.source_id), request.full_sync)
    
    logger.info(
        "Ingestion triggered",
        job_id=str(job.id),
        source_id=str(request.source_id),
        full_sync=request.full_sync,
        task_id=task.id,
    )
    
    return JobResponse(
        id=job.id,
        source_id=job.source_id,
        source_name=source.name,
        type=job.type,
        status=job.status,
        progress=JobProgress(**job.progress) if job.progress else None,
        created_at=job.created_at,
    )


@router.get("/status/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get job status and progress."""
    result = await db.execute(
        select(IngestionJob, Source.name)
        .join(Source)
        .where(IngestionJob.id == job_id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )
    
    job, source_name = row
    
    return JobResponse(
        id=job.id,
        source_id=job.source_id,
        source_name=source_name,
        type=job.type,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        progress=JobProgress(**job.progress) if job.progress else None,
        result=JobResult(**job.result) if job.result else None,
        error=job.error,
        created_by=job.created_by,
        created_at=job.created_at,
    )


@router.post("/cancel/{job_id}")
async def cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Cancel a running job."""
    result = await db.execute(
        select(IngestionJob).where(IngestionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )
    
    if job.status not in ("pending", "running"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status}",
        )
    
    # Update job status
    job.status = "cancelled"
    job.completed_at = datetime.utcnow()
    await db.commit()
    
    # Try to revoke the Celery task
    celery_app.control.revoke(str(job_id), terminate=True)
    
    logger.info("Job cancelled", job_id=str(job_id))
    
    return {"message": "Job cancelled", "job_id": str(job_id)}


@router.post("/process-document")
async def process_document_endpoint(
    request: dict,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Process a single uploaded document (chunk + embed).
    
    Called by Management API after file upload.
    The document should already have its content parsed and stored.
    """
    source_id = request.get("source_id")
    document_id = request.get("document_id")
    
    if not source_id or not document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_id and document_id are required",
        )
    
    # Verify document exists
    result = await db.execute(
        select(Document).where(Document.id == UUID(document_id))
    )
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )
    
    # Queue the processing task
    task = process_uploaded_document.delay(source_id, document_id)
    
    logger.info(
        "Document processing triggered",
        document_id=document_id,
        source_id=source_id,
        task_id=task.id,
    )
    
    return {
        "message": "Document processing started",
        "document_id": document_id,
        "task_id": task.id,
    }


@router.get("/sources/{source_id}/stats")
async def get_source_stats(
    source_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Get source ingestion statistics."""
    result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source not found: {source_id}",
        )
    
    # Get recent jobs
    jobs_result = await db.execute(
        select(IngestionJob)
        .where(IngestionJob.source_id == source_id)
        .order_by(IngestionJob.created_at.desc())
        .limit(10)
    )
    jobs = jobs_result.scalars().all()
    
    return {
        "source_id": source.id,
        "source_name": source.name,
        "document_count": source.document_count,
        "chunk_count": source.chunk_count,
        "last_sync_at": source.last_sync_at,
        "last_sync_status": source.last_sync_status,
        "next_sync_at": source.next_sync_at,
        "recent_jobs": [
            {
                "id": job.id,
                "type": job.type,
                "status": job.status,
                "created_at": job.created_at,
                "completed_at": job.completed_at,
            }
            for job in jobs
        ],
    }
