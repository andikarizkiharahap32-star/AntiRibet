from pydantic import BaseModel
from typing import Generic, TypeVar, Optional, List

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    limit: int
    pages: int


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict] = None


class DashboardStatsResponse(BaseModel):
    total_accounts: int
    total_jobs: int
    discord_success_rate: float
    gmail_success_rate: float
    monthly_cost: float
    active_workers: int
    queue_length: int