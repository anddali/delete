"""
Document management routes.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.services.auth import get_current_user, require_role, AdminUser
from shared.database.connection import get_db
from shared.database.models import Document, DocumentChunk, Source, AuditLog

logger = structlog.get_logger()

router = APIRouter()


# Response models
class DocumentResponse(BaseModel):
    """Document response."""
    id: UUID
    source_id: UUID
    source_name: Optional[str] = None
    external_id: str
    title: str
    content_preview: str
    content_length: int
    url: Optional[str]
    chunk_count: int
    indexed_at: datetime
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(BaseModel):
    """Detailed document response with full content."""
    id: UUID
    source_id: UUID
    source_name: Optional[str] = None
    external_id: str
    title: str
    content: str
    content_hash: Optional[str]
    url: Optional[str]
    metadata: Optional[dict]
    chunk_count: int
    indexed_at: datetime
    created_at: datetime
    updated_at: datetime


class ChunkResponse(BaseModel):
    """Document chunk response."""
    id: UUID
    document_id: UUID
    position: int
    content: str
    char_start: int
    char_end: int
    char_count: int
    has_embedding: bool
    metadata: Optional[dict]
    created_at: datetime


class PaginatedDocumentsResponse(BaseModel):
    """Paginated documents response."""
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class PaginatedChunksResponse(BaseModel):
    """Paginated chunks response."""
    items: List[ChunkResponse]
    total: int
    page: int
    page_size: int
    pages: int


@router.get("", response_model=PaginatedDocumentsResponse)
async def list_documents(
    source_id: Optional[UUID] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all documents with pagination."""
    # Base query
    query = select(Document).options(selectinload(Document.source))
    count_query = select(func.count(Document.id))
    
    # Filters
    if source_id:
        query = query.where(Document.source_id == source_id)
        count_query = count_query.where(Document.source_id == source_id)
    
    if search:
        search_filter = Document.title.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Pagination
    offset = (page - 1) * page_size
    query = query.order_by(Document.created_at.desc()).offset(offset).limit(page_size)
    
    result = await db.execute(query)
    documents = result.scalars().all()
    
    # Get chunk counts for each document
    doc_ids = [d.id for d in documents]
    chunk_counts = {}
    if doc_ids:
        chunk_count_query = (
            select(DocumentChunk.document_id, func.count(DocumentChunk.id))
            .where(DocumentChunk.document_id.in_(doc_ids))
            .group_by(DocumentChunk.document_id)
        )
        chunk_result = await db.execute(chunk_count_query)
        chunk_counts = {row[0]: row[1] for row in chunk_result.all()}
    
    items = [
        DocumentResponse(
            id=doc.id,
            source_id=doc.source_id,
            source_name=doc.source.name if doc.source else None,
            external_id=doc.external_id,
            title=doc.title,
            content_preview=doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
            content_length=len(doc.content),
            url=doc.url,
            chunk_count=chunk_counts.get(doc.id, 0),
            indexed_at=doc.indexed_at,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc in documents
    ]
    
    return PaginatedDocumentsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: UUID,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get document details."""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.source))
        .where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Get chunk count
    chunk_count_result = await db.execute(
        select(func.count(DocumentChunk.id))
        .where(DocumentChunk.document_id == document_id)
    )
    chunk_count = chunk_count_result.scalar() or 0
    
    return DocumentDetailResponse(
        id=doc.id,
        source_id=doc.source_id,
        source_name=doc.source.name if doc.source else None,
        external_id=doc.external_id,
        title=doc.title,
        content=doc.content,
        content_hash=doc.content_hash,
        url=doc.url,
        metadata=doc.doc_metadata,
        chunk_count=chunk_count,
        indexed_at=doc.indexed_at,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/{document_id}/chunks", response_model=PaginatedChunksResponse)
async def list_document_chunks(
    document_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List chunks for a document."""
    # Verify document exists
    doc_result = await db.execute(
        select(Document.id).where(Document.id == document_id)
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    # Get total count
    count_result = await db.execute(
        select(func.count(DocumentChunk.id))
        .where(DocumentChunk.document_id == document_id)
    )
    total = count_result.scalar() or 0
    
    # Get chunks
    offset = (page - 1) * page_size
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.position)
        .offset(offset)
        .limit(page_size)
    )
    chunks = result.scalars().all()
    
    items = [
        ChunkResponse(
            id=chunk.id,
            document_id=chunk.document_id,
            position=chunk.position,
            content=chunk.content,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            char_count=chunk.char_count,
            has_embedding=chunk.embedding is not None,
            metadata=chunk.chunk_metadata,
            created_at=chunk.created_at,
        )
        for chunk in chunks
    ]
    
    return PaginatedChunksResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and its chunks."""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.source))
        .where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    
    source_id = doc.source_id
    doc_title = doc.title
    
    # Delete document (chunks cascade)
    await db.execute(delete(Document).where(Document.id == document_id))
    
    # Update source counts
    from sqlalchemy import update
    await db.execute(
        update(Source)
        .where(Source.id == source_id)
        .values(document_count=Source.document_count - 1)
    )
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="delete",
        resource_type="document",
        resource_id=document_id,
        resource_name=doc_title,
        changes={"source_id": str(source_id)},
    )
    db.add(audit)
    
    await db.commit()
    
    logger.info("Document deleted", document_id=str(document_id), title=doc_title)
