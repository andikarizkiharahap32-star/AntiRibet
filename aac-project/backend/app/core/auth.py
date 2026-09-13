from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password as verify_password_hash

logger = logging.getLogger(__name__)


class TokenData(BaseModel):
    sub: str
    username: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
    type: Optional[str] = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta if expires_delta else timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta if expires_delta else timedelta(hours=settings.JWT_REFRESH_TOKEN_EXPIRE_HOURS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_token_pair(user_id: str, username: str, role: str) -> TokenPair:
    payload = {"sub": user_id, "username": username, "role": role}
    return TokenPair(
        access_token=create_access_token(payload),
        refresh_token=create_refresh_token(payload),
    )


def decode_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return TokenData(**payload)
    except (JWTError, ValidationError) as exc:
        logger.warning(f"Token decode failed: {exc}")
        return None


def verify_access_token(token: str) -> Optional[TokenData]:
    token_data = decode_token(token)
    if token_data and token_data.type == "access":
        return token_data
    return None


def verify_refresh_token(token: str) -> Optional[TokenData]:
    token_data = decode_token(token)
    if token_data and token_data.type == "refresh":
        return token_data
    return None


def hash_password(password: str) -> str:
    return get_password_hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return verify_password_hash(plain_password, hashed_password)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Get current user from JWT access token."""
    from app.models.user import User

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = verify_access_token(token)
    if token_data is None:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(allowed_roles: list[str]):
    """Dependency factory for role-based access control."""

    async def role_checker(current_user=Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {allowed_roles}",
            )
        return current_user

    return role_checker
