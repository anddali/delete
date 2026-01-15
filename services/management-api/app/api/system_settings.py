"""
System settings routes.
"""

from typing import Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import get_current_user, require_role, AdminUser
from shared.database.connection import get_db
from shared.database.models import SystemSetting, AuditLog

logger = structlog.get_logger()

router = APIRouter()


class SettingResponse(BaseModel):
    """Setting response."""
    
    key: str
    value: str
    description: Optional[str]
    is_secret: bool


class SettingUpdate(BaseModel):
    """Setting update request."""
    
    value: str


class SettingCreate(BaseModel):
    """Setting create request."""
    
    key: str
    value: str
    description: Optional[str] = None
    is_secret: bool = False


@router.get("", response_model=List[SettingResponse])
async def list_settings(
    current_user: AdminUser = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """List all system settings."""
    result = await db.execute(
        select(SystemSetting).order_by(SystemSetting.key)
    )
    settings_list = result.scalars().all()
    
    return [
        SettingResponse(
            key=s.key,
            value="********" if s.is_secret else s.value,
            description=s.description,
            is_secret=s.is_secret,
        )
        for s in settings_list
    ]


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    current_user: AdminUser = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific setting."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found",
        )
    
    return SettingResponse(
        key=setting.key,
        value="********" if setting.is_secret else setting.value,
        description=setting.description,
        is_secret=setting.is_secret,
    )


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    request: SettingUpdate,
    current_user: AdminUser = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Update a setting."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found",
        )
    
    old_value = setting.value
    setting.value = request.value
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="update",
        resource_type="setting",
        resource_name=key,
        changes={
            "old_value": "********" if setting.is_secret else old_value,
            "new_value": "********" if setting.is_secret else request.value,
        },
    )
    db.add(audit)
    
    await db.commit()
    
    logger.info("Setting updated", key=key)
    
    return SettingResponse(
        key=setting.key,
        value="********" if setting.is_secret else setting.value,
        description=setting.description,
        is_secret=setting.is_secret,
    )


@router.post("", response_model=SettingResponse, status_code=status.HTTP_201_CREATED)
async def create_setting(
    request: SettingCreate,
    current_user: AdminUser = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new setting."""
    # Check if exists
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == request.key)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Setting already exists",
        )
    
    setting = SystemSetting(
        key=request.key,
        value=request.value,
        description=request.description,
        is_secret=request.is_secret,
    )
    db.add(setting)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="create",
        resource_type="setting",
        resource_name=request.key,
    )
    db.add(audit)
    
    await db.commit()
    
    logger.info("Setting created", key=request.key)
    
    return SettingResponse(
        key=setting.key,
        value="********" if setting.is_secret else setting.value,
        description=setting.description,
        is_secret=setting.is_secret,
    )


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting(
    key: str,
    current_user: AdminUser = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db),
):
    """Delete a setting."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Setting not found",
        )
    
    await db.delete(setting)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="delete",
        resource_type="setting",
        resource_name=key,
    )
    db.add(audit)
    
    await db.commit()
    
    logger.info("Setting deleted", key=key)
