"""
Authentication routes.
"""

from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    verify_password,
    AdminUser as CurrentUser,
)
from shared.database.connection import get_db
from shared.database.models import AdminUser, AuditLog

logger = structlog.get_logger()

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request."""
    
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response."""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """User info response."""
    
    id: str
    email: str
    name: str
    role: str
    created_at: datetime
    last_login_at: Optional[datetime]


class PasswordChangeRequest(BaseModel):
    """Password change request."""
    
    current_password: str
    new_password: str = Field(..., min_length=8)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate admin user."""
    # Find user
    result = await db.execute(
        select(AdminUser).where(
            AdminUser.email == request.email,
            AdminUser.is_active == True,
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(request.password, user.password_hash):
        logger.warning("Failed login attempt", email=request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Create tokens
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id)}
    )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    
    # Audit log
    audit = AuditLog(
        user_id=user.id,
        user_email=user.email,
        action="login",
        resource_type="auth",
        changes={"email": user.email},
    )
    db.add(audit)
    
    await db.commit()
    
    logger.info("User logged in", user_id=str(user.id), email=user.email)
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout user (client should discard tokens)."""
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        user_email=current_user.email,
        action="logout",
        resource_type="auth",
    )
    db.add(audit)
    await db.commit()
    
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get current user info."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.full_name,
        role=current_user.role,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )


@router.put("/password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password."""
    # Get fresh user
    result = await db.execute(
        select(AdminUser).where(AdminUser.id == current_user.id)
    )
    user = result.scalar_one()
    
    # Verify current password
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    # Update password
    user.password_hash = get_password_hash(request.new_password)
    
    # Audit log
    audit = AuditLog(
        user_id=user.id,
        user_email=user.email,
        action="password_change",
        resource_type="auth",
    )
    db.add(audit)
    
    await db.commit()
    
    logger.info("Password changed", user_id=str(user.id))
    
    return {"message": "Password changed successfully"}


@router.post("/refresh")
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token."""
    from jose import jwt, JWTError
    
    try:
        payload = jwt.decode(
            refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        
        # Verify user exists
        result = await db.execute(
            select(AdminUser).where(
                AdminUser.id == user_id,
                AdminUser.is_active == True,
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        # Create new access token
        access_token = create_access_token(
            data={"sub": str(user.id), "role": user.role}
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
