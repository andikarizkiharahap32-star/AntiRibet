"""
Authentication API endpoints
Handles login, logout, token refresh, and session management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash
from app.core.ldap_auth import verify_ldap_user, get_ldap_user_groups
from app.core.auth import get_current_user
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.auth import (
    LoginRequest, LoginResponse, RefreshTokenRequest,
    RefreshTokenResponse, UserResponse
)
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login endpoint with LDAP/SSO support
    - Authenticates via LDAP if enabled
    - Falls back to local authentication
    - Creates JWT access and refresh tokens
    - Logs authentication attempt
    """
    user = None
    auth_method = "local"
    
    # Try LDAP authentication first if enabled
    if settings.LDAP_ENABLED:
        try:
            ldap_valid = await verify_ldap_user(
                login_data.username,
                login_data.password
            )
            
            if ldap_valid:
                auth_method = "ldap"
                # Check LDAP group membership
                user_groups = await get_ldap_user_groups(login_data.username)
                
                if settings.LDAP_ALLOWED_GROUP not in user_groups:
                    # Log failed attempt
                    audit_log = AuditLog(
                        user_id=None,
                        action="login",
                        resource_type="auth",
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                        status="failure",
                        details={"reason": "user not in allowed LDAP group", "username": login_data.username}
                    )
                    db.add(audit_log)
                    await db.commit()
                    
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User not authorized - not in allowed LDAP group"
                    )
                
                # Get or create user from database
                result = await db.execute(
                    select(User).where(User.username == login_data.username)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    # Create new user from LDAP
                    user = User(
                        username=login_data.username,
                        password_hash=get_password_hash(login_data.password),
                        role="operator",  # Default role
                        ldap_dn=f"uid={login_data.username},{settings.LDAP_USER_SEARCH_BASE}",
                        is_active=True
                    )
                    db.add(user)
                    await db.commit()
                    await db.refresh(user)
                else:
                    # Update last login
                    user.last_login = datetime.utcnow()
                    await db.commit()
        
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"LDAP authentication failed for {login_data.username}: {e}")
            # Fall through to local auth
    
    # Local authentication fallback
    if not user:
        result = await db.execute(
            select(User).where(User.username == login_data.username)
        )
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(login_data.password, user.password_hash):
            # Log failed attempt
            audit_log = AuditLog(
                user_id=None,
                action="login",
                resource_type="auth",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                status="failure",
                details={"reason": "invalid credentials", "username": login_data.username}
            )
            db.add(audit_log)
            await db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Update last login
        user.last_login = datetime.utcnow()
        await db.commit()
    
    # Check if user is active
    if not user.is_active:
        # Log failed attempt
        audit_log = AuditLog(
            user_id=user.id,
            action="login",
            resource_type="auth",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            status="failure",
            details={"reason": "user account disabled"}
        )
        db.add(audit_log)
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Create tokens
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    
    # Log successful login
    audit_log = AuditLog(
        user_id=user.id,
        action="login",
        resource_type="auth",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="success",
        details={"auth_method": auth_method}
    )
    db.add(audit_log)
    await db.commit()
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login
        )
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token
    - Validates refresh token
    - Issues new access token
    - Refresh token remains valid
    """
    from jose import JWTError, jwt
    
    try:
        payload = jwt.decode(
            refresh_data.refresh_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Get user
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new access token
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    
    return RefreshTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout endpoint
    - Logs the logout action
    - In production, would invalidate tokens (requires token blacklist)
    """
    # Log logout
    audit_log = AuditLog(
        user_id=current_user.id,
        action="logout",
        resource_type="auth",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="success",
        details={}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )
