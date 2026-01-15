"""
Dashboard routes.
"""

from datetime import datetime, timedelta
from typing import List

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import get_current_user, AdminUser
from shared.database.connection import get_db
from shared.database.models import (
    Source, Document, DocumentChunk, IngestionJob, APIToken, AuditLog, QueryLog
)

logger = structlog.get_logger()

router = APIRouter()


class SystemStats(BaseModel):
    """System statistics."""
    
    total_sources: int
    active_sources: int
    total_documents: int
    total_chunks: int
    total_tokens: int
    active_tokens: int
    jobs_today: int
    jobs_failed_today: int
    queries_today: int


class ActivityItem(BaseModel):
    """Activity log item."""
    
    timestamp: datetime
    action: str
    resource_type: str
    user: str
    changes: dict


class SourceStat(BaseModel):
    """Source statistics."""
    
    id: str
    name: str
    type: str
    document_count: int
    chunk_count: int
    last_sync_at: datetime | None
    status: str


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get system-wide statistics."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Sources
    sources_result = await db.execute(
        select(
            func.count(Source.id).label("total"),
            func.sum(func.cast(Source.is_active, type_=int)).label("active"),
        )
    )
    sources_row = sources_result.one()
    
    # Documents
    docs_result = await db.execute(select(func.count(Document.id)))
    total_documents = docs_result.scalar() or 0
    
    # Chunks
    chunks_result = await db.execute(select(func.count(DocumentChunk.id)))
    total_chunks = chunks_result.scalar() or 0
    
    # Tokens
    tokens_result = await db.execute(
        select(
            func.count(APIToken.id).label("total"),
            func.sum(func.cast(APIToken.is_active, type_=int)).label("active"),
        )
    )
    tokens_row = tokens_result.one()
    
    # Jobs today
    jobs_result = await db.execute(
        select(
            func.count(IngestionJob.id).label("total"),
            func.sum(
                func.cast(IngestionJob.status == "failed", type_=int)
            ).label("failed"),
        ).where(IngestionJob.created_at >= today_start)
    )
    jobs_row = jobs_result.one()
    
    # Queries today
    queries_result = await db.execute(
        select(func.count(QueryLog.id)).where(QueryLog.created_at >= today_start)
    )
    queries_today = queries_result.scalar() or 0
    
    return SystemStats(
        total_sources=sources_row.total or 0,
        active_sources=int(sources_row.active or 0),
        total_documents=total_documents,
        total_chunks=total_chunks,
        total_tokens=tokens_row.total or 0,
        active_tokens=int(tokens_row.active or 0),
        jobs_today=jobs_row.total or 0,
        jobs_failed_today=int(jobs_row.failed or 0),
        queries_today=queries_today,
    )


@router.get("/activity", response_model=List[ActivityItem])
async def get_recent_activity(
    limit: int = 20,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent activity from audit log."""
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    
    # Get user names
    user_ids = [log.user_id for log in logs if log.user_id]
    users = {}
    
    if user_ids:
        from shared.database.models import AdminUser as AdminUserModel
        user_result = await db.execute(
            select(AdminUserModel).where(AdminUserModel.id.in_(user_ids))
        )
        users = {u.id: u.full_name for u in user_result.scalars().all()}
    
    return [
        ActivityItem(
            timestamp=log.created_at,
            action=log.action,
            resource_type=log.resource_type,
            user=users.get(log.user_id, "System"),
            changes=log.changes or {},
        )
        for log in logs
    ]


@router.get("/sources/stats", response_model=List[SourceStat])
async def get_source_stats(
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for all sources."""
    result = await db.execute(
        select(Source).order_by(Source.name)
    )
    sources = result.scalars().all()
    
    return [
        SourceStat(
            id=str(s.id),
            name=s.name,
            type=s.type,
            document_count=s.document_count or 0,
            chunk_count=s.chunk_count or 0,
            last_sync_at=s.last_sync_at,
            status="active" if s.is_active else "inactive",
        )
        for s in sources
    ]


@router.get("/queries/stats")
async def get_query_stats(
    days: int = 7,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get query statistics for the past N days."""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Daily query counts
    daily_result = await db.execute(
        select(
            func.date(QueryLog.created_at).label("date"),
            func.count(QueryLog.id).label("count"),
            func.avg(QueryLog.search_time_ms).label("avg_time"),
        )
        .where(QueryLog.created_at >= start_date)
        .group_by(func.date(QueryLog.created_at))
        .order_by(func.date(QueryLog.created_at))
    )
    daily_stats = [
        {
            "date": row.date.isoformat(),
            "count": row.count,
            "avg_time_ms": float(row.avg_time) if row.avg_time else 0,
        }
        for row in daily_result.fetchall()
    ]
    
    # Top queries
    top_result = await db.execute(
        select(
            QueryLog.query,
            func.count(QueryLog.id).label("count"),
        )
        .where(QueryLog.created_at >= start_date)
        .group_by(QueryLog.query)
        .order_by(func.count(QueryLog.id).desc())
        .limit(10)
    )
    top_queries = [
        {"query": row.query, "count": row.count}
        for row in top_result.fetchall()
    ]
    
    return {
        "daily": daily_stats,
        "top_queries": top_queries,
    }
