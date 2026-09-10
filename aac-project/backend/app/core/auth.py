from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from pydantic import BaseModel
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class TokenData(BaseModel):
    sub: str
    username: str
    role: str
    exp: int
    iat: int
    type: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_REFRESH_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_token_pair(user_id: str, username: str, role: str) -> TokenPair:
    data = {"sub": user_id, "username": username, "role": role}
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


def decode_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return TokenData(**payload)
    except JWTError as e:
        logger.warning(f"Token decode failed: {e}")
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
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)


# FastAPI dependency injection functions
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(None)  # Will be injected from database module
):
    """
    Get current user from JWT token
    - Validates token
    - Returns User model
    """
    from app.core.database import get_db
    from app.models.user import User
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = verify_access_token(token)
    if token_data is None:
        raise credentials_exception
    
    # Get database session if not provided
    if db is None:
        async for session in get_db():
            db = session
            break
    
    # Get user from database
    result = await db.execute(
        select(User).where(User.id == token_data.sub)
    )
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        raise credentials_exception
    
    return user


def require_role(allowed_roles: list[str]):
    """
    Dependency factory for role-based access control
    Usage: current_user = Depends(require_role(["admin", "operator"]))
    """
    async def role_checker(current_user = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {allowed_roles}"
            )
        return current_user
    
    return role_checker