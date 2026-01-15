"""
Source management routes.
"""

import os
import aiofiles
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.auth import get_current_user, require_role, AdminUser
from shared.database.connection import get_db
from shared.database.models import Source, Document, DocumentChunk, IngestionJob, AuditLog
from shared.utils.security import encrypt_credentials

logger = structlog.get_logger()

router = APIRouter()

# Upload storage directory
UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# Request/Response models
class SourceConfig(BaseModel):
    """Source configuration."""
    
    # Confluence
    base_url: Optional[str] = None
    space_keys: Optional[List[str]] = None
    
    # Slack
    workspace_id: Optional[str] = None
    channel_ids: Optional[List[str]] = None
    
    # File upload
    bucket: Optional[str] = None
    prefix: Optional[str] = None
    allowed_extensions: Optional[List[str]] = None


class SourceCredentials(BaseModel):
    """Source credentials (encrypted at rest)."""
    
    # Confluence
    email: Optional[str] = None
    api_token: Optional[str] = None
    
    # Slack
    bot_token: Optional[str] = None


class SourceCreate(BaseModel):
    """Create source request."""
    
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., pattern="^(confluence|slack|file_upload)$")
    config: SourceConfig
    credentials: Optional[SourceCredentials] = None
    sync_frequency: str = Field(default="0 */6 * * *")  # Cron
    chunking_config: Optional[dict] = None


class SourceUpdate(BaseModel):
    """Update source request."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    config: Optional[SourceConfig] = None
    credentials: Optional[SourceCredentials] = None
    sync_frequency: Optional[str] = None
    chunking_config: Optional[dict] = None
    is_active: Optional[bool] = None


class SourceResponse(BaseModel):
    """Source response."""
    
    id: UUID
    name: str
    type: str
    is_active: bool
    document_count: int
    chunk_count: int
    last_sync_at: Optional[datetime]
    last_sync_status: Optional[str]
    next_sync_at: Optional[datetime]
    sync_frequency: Optional[str]
    created_at: datetime
    updated_at: datetime


class SourceDetailResponse(SourceResponse):
    """Detailed source response."""
    
    config: dict
    chunking_config: Optional[dict]


@router.get("", response_model=List[SourceResponse])
async def list_sources(
    type: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all sources."""
    query = select(Source)
    
    if type:
        query = query.where(Source.type == type)
    if is_active is not None:
        query = query.where(Source.is_active == is_active)
    
    query = query.order_by(Source.name)
    
    result = await db.execute(query)
    sources = result.scalars().all()
    
    return [
        SourceResponse(
            id=s.id,
            name=s.name,
            type=s.type,
            is_active=s.is_active,
            document_count=s.document_count or 0,
            chunk_count=s.chunk_count or 0,
            last_sync_at=s.last_sync_at,
            last_sync_status=s.last_sync_status,
            next_sync_at=s.next_sync_at,
            sync_frequency=s.sync_frequency,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sources
    ]


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    request: SourceCreate,
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Create new source."""
    # Build config
    config = request.config.model_dump(exclude_none=True)
    
    # Encrypt credentials
    if request.credentials:
        credentials = request.credentials.model_dump(exclude_none=True)
        if credentials:
            config["credentials"] = encrypt_credentials(credentials)
    
    # Add chunking config to the config JSONB field
    config["chunking"] = request.chunking_config or {
        "chunk_size_chars": 1000,
        "respect_boundaries": True,
        "min_chunk_size_chars": 200,
    }
    
    # Create source
    source = Source(
        name=request.name,
        type=request.type,
        config=config,
        sync_frequency=request.sync_frequency,
    )
    db.add(source)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="create",
        resource_type="source",
        resource_id=source.id,
        resource_name=source.name,
        changes={"name": source.name, "type": source.type},
    )
    db.add(audit)
    
    await db.commit()
    await db.refresh(source)
    
    logger.info("Source created", source_id=str(source.id), name=source.name)
    
    return SourceResponse(
        id=source.id,
        name=source.name,
        type=source.type,
        is_active=source.is_active,
        document_count=0,
        chunk_count=0,
        last_sync_at=None,
        last_sync_status=None,
        next_sync_at=source.next_sync_at,
        sync_frequency=source.sync_frequency,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.get("/{source_id}", response_model=SourceDetailResponse)
async def get_source(
    source_id: UUID,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get source details."""
    result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    
    # Remove credentials from response
    config = dict(source.config) if source.config else {}
    config.pop("credentials", None)
    
    return SourceDetailResponse(
        id=source.id,
        name=source.name,
        type=source.type,
        is_active=source.is_active,
        document_count=source.document_count or 0,
        chunk_count=source.chunk_count or 0,
        last_sync_at=source.last_sync_at,
        last_sync_status=source.last_sync_status,
        next_sync_at=source.next_sync_at,
        sync_frequency=source.sync_frequency,
        created_at=source.created_at,
        updated_at=source.updated_at,
        config=config,
        chunking_config=source.chunking_config,
    )


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: UUID,
    request: SourceUpdate,
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Update source."""
    result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    
    # Update fields
    if request.name is not None:
        source.name = request.name
    
    if request.config is not None:
        config = source.config or {}
        config.update(request.config.model_dump(exclude_none=True))
        source.config = config
    
    if request.credentials is not None:
        credentials = request.credentials.model_dump(exclude_none=True)
        if credentials:
            config = source.config or {}
            config["credentials"] = encrypt_credentials(credentials)
            source.config = config
    
    if request.sync_frequency is not None:
        source.sync_frequency = request.sync_frequency
    
    if request.chunking_config is not None:
        source.chunking_config = request.chunking_config
    
    if request.is_active is not None:
        source.is_active = request.is_active
    
    source.updated_at = datetime.utcnow()
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="update",
        resource_type="source",
        resource_id=source.id,
        resource_name=source.name,
        changes=request.model_dump(exclude_none=True, exclude={"credentials"}),
    )
    db.add(audit)
    
    await db.commit()
    await db.refresh(source)
    
    logger.info("Source updated", source_id=str(source.id))
    
    return SourceResponse(
        id=source.id,
        name=source.name,
        type=source.type,
        is_active=source.is_active,
        document_count=source.document_count or 0,
        chunk_count=source.chunk_count or 0,
        last_sync_at=source.last_sync_at,
        last_sync_status=source.last_sync_status,
        next_sync_at=source.next_sync_at,
        sync_frequency=source.sync_frequency,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: UUID,
    current_user: AdminUser = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete source (soft delete - deactivates and removes data)."""
    result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    
    # Soft delete - deactivate
    source.is_active = False
    source.updated_at = datetime.utcnow()
    
    # Optionally delete documents and chunks
    # This cascades due to FK relationships
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="delete",
        resource_type="source",
        resource_id=source.id,
        resource_name=source.name,
        changes={"name": source.name},
    )
    db.add(audit)
    
    await db.commit()
    
    logger.info("Source deleted", source_id=str(source_id))


@router.post("/{source_id}/sync")
async def trigger_sync(
    source_id: UUID,
    full_sync: bool = False,
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Trigger source sync."""
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.is_active == True)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found or inactive",
        )
    
    # Call ingestion service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.INGESTION_SERVICE_URL}/ingest/trigger",
                json={
                    "source_id": str(source_id),
                    "full_sync": full_sync,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
    
    except httpx.HTTPError as e:
        logger.error("Failed to trigger sync", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion service unavailable",
        )
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="sync_trigger",
        resource_type="source",
        resource_id=source.id,
        resource_name=source.name,
        changes={"full_sync": full_sync, "job_id": data.get("job_id")},
    )
    db.add(audit)
    await db.commit()
    
    return {
        "message": "Sync triggered",
        "job_id": data.get("job_id"),
    }


@router.post("/{source_id}/test")
async def test_connection(
    source_id: UUID,
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Test source connection."""
    result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    
    # Call ingestion service to test
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.INGESTION_SERVICE_URL}/ingest/test",
                json={"source_id": str(source_id)},
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
    
    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": str(e),
        }
    
    return {
        "success": data.get("success", False),
        "message": data.get("message", "Connection test completed"),
    }


# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".doc", ".html", ".json", ".csv", ".xml"}


class FileUploadResponse(BaseModel):
    """File upload response."""
    document_id: UUID
    filename: str
    size: int
    message: str


@router.post("/{source_id}/upload", response_model=FileUploadResponse)
async def upload_file(
    source_id: UUID,
    file: UploadFile = File(...),
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file to a file_upload source."""
    # Get source
    result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    
    if source.type != "file_upload":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source is not a file upload source",
        )
    
    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source is not active",
        )
    
    # Validate file extension
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {ext} not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    
    # Create source directory
    source_upload_dir = os.path.join(UPLOAD_DIR, str(source_id))
    os.makedirs(source_upload_dir, exist_ok=True)
    
    # Generate unique filename
    import uuid as uuid_mod
    unique_filename = f"{uuid_mod.uuid4()}{ext}"
    file_path = os.path.join(source_upload_dir, unique_filename)
    
    # Save file and read content
    file_size = 0
    file_content = b""
    async with aiofiles.open(file_path, 'wb') as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            await f.write(chunk)
            file_content += chunk
            file_size += len(chunk)
    
    # Try to decode content as text
    try:
        text_content = file_content.decode('utf-8')
    except UnicodeDecodeError:
        text_content = f"[Binary file: {filename}]"
    
    # Create document record
    doc = Document(
        source_id=source_id,
        external_id=unique_filename,
        title=filename,
        content=text_content,
        url=file_path,
        doc_metadata={"original_filename": filename, "size": file_size, "content_type": file.content_type or "application/octet-stream"},
    )
    db.add(doc)
    
    # Update source document count
    await db.execute(
        update(Source)
        .where(Source.id == source_id)
        .values(document_count=Source.document_count + 1)
    )
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="upload",
        resource_type="document",
        resource_id=doc.id,
        resource_name=filename,
        changes={"source_id": str(source_id), "size": file_size},
    )
    db.add(audit)
    
    await db.commit()
    await db.refresh(doc)
    
    logger.info("File uploaded", document_id=str(doc.id), filename=filename, size=file_size)
    
    return FileUploadResponse(
        document_id=doc.id,
        filename=filename,
        size=file_size,
        message="File uploaded successfully. It will be processed shortly.",
    )


@router.post("/{source_id}/upload-multiple")
async def upload_multiple_files(
    source_id: UUID,
    files: List[UploadFile] = File(...),
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Upload multiple files to a file_upload source."""
    # Get source
    result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    
    if source.type != "file_upload":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source is not a file upload source",
        )
    
    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source is not active",
        )
    
    source_upload_dir = os.path.join(UPLOAD_DIR, str(source_id))
    os.makedirs(source_upload_dir, exist_ok=True)
    
    import uuid as uuid_mod
    uploaded = []
    errors = []
    
    for file in files:
        filename = file.filename or "unknown"
        ext = os.path.splitext(filename)[1].lower()
        
        if ext not in ALLOWED_EXTENSIONS:
            errors.append({"filename": filename, "error": f"File type {ext} not allowed"})
            continue
        
        try:
            unique_filename = f"{uuid_mod.uuid4()}{ext}"
            file_path = os.path.join(source_upload_dir, unique_filename)
            
            file_size = 0
            file_content = b""
            async with aiofiles.open(file_path, 'wb') as f:
                while chunk := await file.read(1024 * 1024):
                    await f.write(chunk)
                    file_content += chunk
                    file_size += len(chunk)
            
            # Try to decode content as text
            try:
                text_content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                text_content = f"[Binary file: {filename}]"
            
            doc = Document(
                source_id=source_id,
                external_id=unique_filename,
                title=filename,
                content=text_content,
                url=file_path,
                doc_metadata={"original_filename": filename, "size": file_size, "content_type": file.content_type or "application/octet-stream"},
            )
            db.add(doc)
            
            uploaded.append({
                "document_id": str(doc.id),
                "filename": filename,
                "size": file_size,
            })
        except Exception as e:
            errors.append({"filename": filename, "error": str(e)})
    
    if uploaded:
        # Update source document count
        await db.execute(
            update(Source)
            .where(Source.id == source_id)
            .values(document_count=Source.document_count + len(uploaded))
        )
        
        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            user_email=current_user.email,
            action="upload_multiple",
            resource_type="source",
            resource_id=source_id,
            resource_name=source.name,
            changes={"files_uploaded": len(uploaded)},
        )
        db.add(audit)
        
        await db.commit()
    
    return {
        "uploaded": uploaded,
        "errors": errors,
        "total_uploaded": len(uploaded),
        "total_errors": len(errors),
    }


@router.post("/{source_id}/process")
async def process_uploaded_files(
    source_id: UUID,
    current_user: AdminUser = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db),
):
    """Trigger processing of uploaded files for a source."""
    result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    
    if source.type != "file_upload":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source is not a file upload source",
        )
    
    # Get pending documents
    result = await db.execute(
        select(Document).where(
            Document.source_id == source_id,
            Document.status == "pending"
        )
    )
    pending_docs = result.scalars().all()
    
    if not pending_docs:
        return {"message": "No pending documents to process"}
    
    # Call ingestion service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.INGESTION_SERVICE_URL}/ingest/trigger",
                json={"source_id": str(source_id)},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to trigger ingestion: {str(e)}",
        )
    
    return {
        "message": f"Processing triggered for {len(pending_docs)} documents",
        "job_id": data.get("job_id"),
        "pending_count": len(pending_docs),
    }

