from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCreate(BaseModel):
    platform: str = Field(..., pattern="^(discord|gmail)$")
    total_count: int = Field(..., ge=1, le=1000)
    proxy_provider: Optional[str] = Field("brightdata", max_length=50)
    sms_provider: Optional[str] = Field("5sim", max_length=50)
    captcha_provider: Optional[str] = Field("2captcha", max_length=50)

    @property
    def type(self) -> str:
        return self.platform


class JobUpdate(BaseModel):
    status: Optional[str] = None
    success_count: Optional[int] = None
    failed_count: Optional[int] = None
    cancelled_count: Optional[int] = None
    last_successful_index: Optional[int] = None
    finished_at: Optional[datetime] = None


class JobResponse(BaseModel):
    id: uuid.UUID
    status: str
    total_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class JobDetailResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    total_count: int
    success_count: int
    failed_count: int
    cancelled_count: int
    status: str
    proxy_provider: Optional[str]
    sms_provider: Optional[str]
    captcha_provider: Optional[str]
    last_successful_index: int
    created_at: datetime
    finished_at: Optional[datetime]
    estimated_cost: float
    
    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    limit: int


class JobStats(BaseModel):
    total_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    total_accounts_created: int = 0
    discord_success_rate: float = 0.0
    gmail_success_rate: float = 0.0
