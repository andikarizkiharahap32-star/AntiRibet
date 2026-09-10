from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
import uuid


class AccountResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    platform: str
    email: str
    username: str
    password: Optional[str] = None  # Only included in export or detail view
    token: Optional[str] = None
    status: str
    proxy_used: Optional[str] = None
    created_at: datetime
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class AccountListResponse(BaseModel):
    accounts: List[AccountResponse]
    total: int
    page: int
    limit: int