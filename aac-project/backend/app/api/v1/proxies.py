"""
Proxies API endpoints
Handles proxy management and monitoring
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
import logging

from app.core.database import get_db
from app.core.auth import require_role
from app.models.user import User
from app.models.proxy import Proxy
from app.models.audit_log import AuditLog
from app.schemas.proxy import (
    ProxyCreate, ProxyResponse, ProxyListResponse,
    ProxyStatsResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=ProxyResponse, status_code=status.HTTP_201_CREATED)
async def add_proxy(
    request: Request,
    proxy_data: ProxyCreate,
    current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a new proxy to the pool
    - Admin only
    - Validates proxy format
    """
    proxy = Proxy(
        url=proxy_data.url,
        provider=proxy_data.provider,
        type=proxy_data.type,
        status="active"
    )
    
    db.add(proxy)
    await db.commit()
    await db.refresh(proxy)
    
    # Log action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="add_proxy",
        resource_type="proxy",
        resource_id=str(proxy.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="success",
        details={"provider": proxy_data.provider, "type": proxy_data.type}
    )
    db.add(audit_log)
    await db.commit()
    
    return ProxyResponse(
        id=proxy.id,
        url=proxy.url,
        provider=proxy.provider,
        type=proxy.type,
        status=proxy.status,
        success_count=proxy.success_count,
        fail_count=proxy.fail_count,
        last_used=proxy.last_used,
        last_checked=proxy.last_checked,
        response_time_ms=proxy.response_time_ms,
        created_at=proxy.created_at
    )


@router.get("", response_model=ProxyListResponse)
async def list_proxies(
    status_filter: Optional[str] = Query(None, alias="status"),
    provider: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db)
):
    """
    List all proxies with filters
    """
    query = select(Proxy)
    
    if status_filter:
        query = query.where(Proxy.status == status_filter)
    
    if provider:
        query = query.where(Proxy.provider == provider)
    
    # Count total
    count_query = select(func.count()).select_from(Proxy)
    if status_filter:
        count_query = count_query.where(Proxy.status == status_filter)
    if provider:
        count_query = count_query.where(Proxy.provider == provider)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Paginate
    query = query.order_by(Proxy.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await db.execute(query)
    proxies = result.scalars().all()
    
    return ProxyListResponse(
        proxies=[
            ProxyResponse(
                id=proxy.id,
                url=proxy.url,
                provider=proxy.provider,
                type=proxy.type,
                status=proxy.status,
                success_count=proxy.success_count,
                fail_count=proxy.fail_count,
                last_used=proxy.last_used,
                last_checked=proxy.last_checked,
                response_time_ms=proxy.response_time_ms,
                created_at=proxy.created_at
            ) for proxy in proxies
        ],
        total=total
    )


@router.get("/stats", response_model=ProxyStatsResponse)
async def get_proxy_stats(
    current_user: User = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Get proxy statistics
    - Total proxies by status
    - Average success rate
    - Top performing proxies
    """
    # Count by status
    active_result = await db.execute(
        select(func.count()).select_from(Proxy).where(Proxy.status == "active")
    )
    active_count = active_result.scalar()
    
    dead_result = await db.execute(
        select(func.count()).select_from(Proxy).where(Proxy.status == "dead")
    )
    dead_count = dead_result.scalar()
    
    total_result = await db.execute(
        select(func.count()).select_from(Proxy)
    )
    total_count = total_result.scalar()
    
    # Calculate average success rate
    proxies_result = await db.execute(
        select(Proxy).where(Proxy.status == "active")
    )
    proxies = proxies_result.scalars().all()
    
    avg_success_rate = 0.0
    if proxies:
        success_rates = [
            p.success_count / (p.success_count + p.fail_count)
            if (p.success_count + p.fail_count) > 0 else 0
            for p in proxies
        ]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0
    
    # Get top 10 proxies
    top_proxies_result = await db.execute(
        select(Proxy)
        .where(Proxy.status == "active")
        .order_by((Proxy.success_count).desc())
        .limit(10)
    )
    top_proxies = top_proxies_result.scalars().all()
    
    return ProxyStatsResponse(
        total_proxies=total_count,
        active=active_count,
        dead=dead_count,
        average_success_rate=round(avg_success_rate, 4),
        top_proxies=[
            ProxyResponse(
                id=proxy.id,
                url=proxy.url,
                provider=proxy.provider,
                type=proxy.type,
                status=proxy.status,
                success_count=proxy.success_count,
                fail_count=proxy.fail_count,
                last_used=proxy.last_used,
                last_checked=proxy.last_checked,
                response_time_ms=proxy.response_time_ms,
                created_at=proxy.created_at
            ) for proxy in top_proxies
        ]
    )
