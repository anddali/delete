"""
Celery tasks for document ingestion.
"""

import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import structlog
from celery import Task
from sqlalchemy import delete, select, update

from app.config import settings
from app.plugins import get_plugin
from app.services.chunking import chunk_document, get_chunking_config
from app.services.embedding import generate_embeddings
from app.workers.celery_app import celery_app
from shared.database.connection import DatabaseSessionManager
from shared.database.models import Document, DocumentChunk, IngestionJob, Source

logger = structlog.get_logger()


def run_async(coro):
    """Run async code in sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class CallbackTask(Task):
    """Base task with error handling and retry logic."""
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


@celery_app.task(bind=True, base=CallbackTask)
def ingest_source(
    self,
    job_id: str,
    source_id: str,
    full_sync: bool = False,
):
    """Main ingestion task for a source."""
    return run_async(_ingest_source_async(self, job_id, source_id, full_sync))


async def _ingest_source_async(
    task,
    job_id: str,
    source_id: str,
    full_sync: bool,
):
    """Async implementation of ingestion."""
    session_manager = DatabaseSessionManager()
    session_manager.init(settings.DATABASE_URL)
    
    try:
        async with session_manager.session() as db:
            # Get job and update status
            job = await db.get(IngestionJob, UUID(job_id))
            if not job:
                logger.error("Job not found", job_id=job_id)
                return
            
            # Update job to running
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.progress = {"processed": 0, "total": None, "current_step": "fetching"}
            await db.commit()
            
            # Get source
            source = await db.get(Source, UUID(source_id))
            if not source:
                await _update_job_failed(db, job, "Source not found")
                return
            
            try:
                # Get plugin for source type
                plugin = get_plugin(source.type, source.config)
                
                # Get chunking config
                chunking_config = get_chunking_config(source.config)
                
                # Fetch documents
                if full_sync:
                    documents = plugin.fetch_initial()
                else:
                    since = source.last_sync_at or datetime.min
                    documents = plugin.fetch_updates(since=since)
                
                # Process documents
                processed = 0
                added = 0
                updated = 0
                deleted = 0
                errors = []
                
                async for doc_data in documents:
                    try:
                        result = await _process_document(
                            db, source, doc_data, chunking_config
                        )
                        if result == "added":
                            added += 1
                        elif result == "updated":
                            updated += 1
                        processed += 1
                        
                        # Update progress
                        if processed % 10 == 0:
                            job.progress = {
                                "processed": processed,
                                "total": None,
                                "current_step": f"processing document {processed}",
                            }
                            await db.commit()
                    
                    except Exception as e:
                        logger.error(
                            "Failed to process document",
                            error=str(e),
                            doc_id=doc_data.get("external_id"),
                        )
                        errors.append(str(e))
                
                # Update source stats
                source.last_sync_at = datetime.utcnow()
                source.last_sync_status = "success"
                
                # Count documents and chunks
                doc_count_result = await db.execute(
                    select(Document).where(Document.source_id == source.id)
                )
                source.document_count = len(doc_count_result.scalars().all())
                
                chunk_count_result = await db.execute(
                    select(DocumentChunk)
                    .join(Document)
                    .where(Document.source_id == source.id)
                )
                source.chunk_count = len(chunk_count_result.scalars().all())
                
                # Complete job
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                job.progress = {"processed": processed, "total": processed, "current_step": "completed"}
                job.result = {
                    "documents_added": added,
                    "documents_updated": updated,
                    "documents_deleted": deleted,
                    "chunks_created": source.chunk_count,
                    "errors": errors[:10],  # Limit errors
                }
                
                await db.commit()
                
                logger.info(
                    "Ingestion completed",
                    job_id=job_id,
                    source_id=source_id,
                    processed=processed,
                    added=added,
                    updated=updated,
                )
                
            except Exception as e:
                await _update_job_failed(db, job, str(e))
                source.last_sync_status = "failed"
                await db.commit()
                raise
    
    finally:
        await session_manager.close()


async def _process_document(
    db,
    source: Source,
    doc_data: dict,
    chunking_config: dict,
) -> str:
    """
    Process a single document: parse, chunk, embed, store.
    
    Returns:
        "added" if new document, "updated" if existing, "skipped" if unchanged
    """
    external_id = doc_data["external_id"]
    content = doc_data["content"]
    title = doc_data.get("title", "Untitled")
    url = doc_data.get("url")
    metadata = doc_data.get("metadata", {})
    
    # Calculate content hash for change detection
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    
    # Check if document exists
    result = await db.execute(
        select(Document).where(
            Document.source_id == source.id,
            Document.external_id == external_id,
        )
    )
    existing_doc = result.scalar_one_or_none()
    
    if existing_doc:
        # Check if content changed
        if existing_doc.content_hash == content_hash:
            return "skipped"
        
        # Delete existing chunks
        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == existing_doc.id)
        )
        
        # Update document
        existing_doc.title = title
        existing_doc.content = content
        existing_doc.content_hash = content_hash
        existing_doc.url = url
        existing_doc.metadata = metadata
        existing_doc.indexed_at = datetime.utcnow()
        
        document = existing_doc
        action = "updated"
    else:
        # Create new document
        document = Document(
            source_id=source.id,
            external_id=external_id,
            title=title,
            content=content,
            content_hash=content_hash,
            url=url,
            metadata=metadata,
        )
        db.add(document)
        await db.flush()
        action = "added"
    
    # Chunk the document (NO OVERLAP)
    chunks = chunk_document(
        content=content,
        chunk_size_chars=chunking_config["chunk_size_chars"],
        respect_boundaries=chunking_config["respect_boundaries"],
        min_chunk_size_chars=chunking_config["min_chunk_size_chars"],
        metadata={"source_id": str(source.id), "document_id": str(document.id)},
    )
    
    if chunks:
        # Generate embeddings in batch
        chunk_texts = [c.content for c in chunks]
        embeddings = await generate_embeddings(chunk_texts)
        
        # Create chunk records
        for chunk, embedding in zip(chunks, embeddings):
            chunk_record = DocumentChunk(
                document_id=document.id,
                content=chunk.content,
                embedding=embedding,
                position=chunk.position,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                char_count=chunk.char_count,
                metadata=chunk.metadata,
            )
            db.add(chunk_record)
    
    await db.commit()
    return action


async def _update_job_failed(db, job: IngestionJob, error: str):
    """Update job status to failed."""
    job.status = "failed"
    job.completed_at = datetime.utcnow()
    job.error = error
    await db.commit()
    logger.error("Ingestion failed", job_id=str(job.id), error=error)


@celery_app.task
def scheduled_sync():
    """Find sources due for sync and trigger ingestion."""
    return run_async(_scheduled_sync_async())


async def _scheduled_sync_async():
    """Async implementation of scheduled sync."""
    session_manager = DatabaseSessionManager()
    session_manager.init(settings.DATABASE_URL)
    
    try:
        async with session_manager.session() as db:
            # Find sources due for sync
            now = datetime.utcnow()
            result = await db.execute(
                select(Source).where(
                    Source.is_active == True,
                    Source.next_sync_at <= now,
                )
            )
            sources = result.scalars().all()
            
            for source in sources:
                # Create job
                job = IngestionJob(
                    source_id=source.id,
                    type="incremental",
                    status="pending",
                )
                db.add(job)
                await db.flush()
                
                # Queue the task
                ingest_source.delay(str(job.id), str(source.id), False)
                
                # Update next sync time
                # Parse cron expression or use default interval
                source.next_sync_at = now + timedelta(hours=6)
                
                logger.info(
                    "Scheduled sync triggered",
                    source_id=str(source.id),
                    job_id=str(job.id),
                )
            
            await db.commit()
    
    finally:
        await session_manager.close()


@celery_app.task
def cleanup_old_jobs():
    """Clean up old completed jobs."""
    return run_async(_cleanup_old_jobs_async())


async def _cleanup_old_jobs_async():
    """Async implementation of job cleanup."""
    session_manager = DatabaseSessionManager()
    session_manager.init(settings.DATABASE_URL)
    
    try:
        async with session_manager.session() as db:
            cutoff = datetime.utcnow() - timedelta(days=30)
            
            result = await db.execute(
                delete(IngestionJob).where(
                    IngestionJob.created_at < cutoff,
                    IngestionJob.status.in_(["completed", "failed", "cancelled"]),
                )
            )
            
            await db.commit()
            
            logger.info("Cleaned up old jobs", deleted=result.rowcount)
    
    finally:
        await session_manager.close()
