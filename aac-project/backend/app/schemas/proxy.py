from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ProxyBase(BaseModel):
    url: str = Field(..., min_length=1)
    provider: str = Field(..., max_length=50)
    type: str = Field(..., pattern="^(residential|datacenter)$")


class ProxyCreate(ProxyBase):
    pass


class ProxyUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(active|inactive|dead)$")
    provider: Optional[str] = Field(None, max_length=50)
    type: Optional[str] = Field(None, pattern="^(residential|datacenter)$")


class ProxyResponse(ProxyBase):
    id: int
    status: str
    success_count: int
    fail_count: int
    last_used: Optional[datetime]
    last_checked: Optional[datetime]
    response_time_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ProxyListResponse(BaseModel):
    proxies: List[ProxyResponse]
    total: int


class ProxyStatsResponse(BaseModel):
    total_proxies: int
    active: int
    dead: int
    average_success_rate: float
    top_proxies: List[ProxyResponse]