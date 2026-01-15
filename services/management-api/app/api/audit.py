"""
Audit log routes.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import get_current_user, require_role, AdminUser
from shared.database.connection import get_db
from shared.database.models import AuditLog
from shared.database.models import AdminUser as AdminUserModel

logger = structlog.get_logger()

router = APIRouter()


class AuditLogEntry(BaseModel):
    """Audit log entry."""
    
    id: UUID
    timestamp: datetime
    user_id: Optional[UUID]
    user_name: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[UUID]
    changes: Optional[dict]
    ip_address: Optional[str]


class AuditLogResponse(BaseModel):
    """Paginated audit log response."""
    
    items: List[AuditLogEntry]
    total: int
    page: int
    page_size: int


@router.get("", response_model=AuditLogResponse)
async def list_audit_logs(
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: AdminUser = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List audit log entries with filtering."""
    # Build query
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))
    
    # Apply filters
    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
        count_query = count_query.where(AuditLog.resource_type == resource_type)
    
    if user_id:
        query = query.where(AuditLog.admin_user_id == user_id)
        count_query = count_query.where(AuditLog.admin_user_id == user_id)
    
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
        count_query = count_query.where(AuditLog.created_at >= start_date)
    
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)
        count_query = count_query.where(AuditLog.created_at <= end_date)
    
    # Count total
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.order_by(AuditLog.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    # Get user names
    user_ids = [log.user_id for log in logs if log.user_id]
    users = {}
    
    if user_ids:
        user_result = await db.execute(
            select(AdminUserModel).where(AdminUserModel.id.in_(user_ids))
        )
        users = {u.id: u.full_name for u in user_result.scalars().all()}
    
    return AuditLogResponse(
        items=[
            AuditLogEntry(
                id=log.id,
                timestamp=log.created_at,
                user_id=log.user_id,
                user_name=users.get(log.user_id),
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                changes=log.changes,
                ip_address=log.ip_address,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/actions")
async def list_action_types(
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List distinct action types."""
    result = await db.execute(
        select(AuditLog.action).distinct()
    )
    actions = [row[0] for row in result.fetchall()]
    return {"actions": actions}


@router.get("/resource-types")
async def list_resource_types(
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List distinct resource types."""
    result = await db.execute(
        select(AuditLog.resource_type).distinct()
    )
    types = [row[0] for row in result.fetchall()]
    return {"resource_types": types}
