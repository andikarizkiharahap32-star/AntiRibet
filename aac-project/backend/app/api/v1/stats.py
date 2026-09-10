"""
Statistics API endpoints
Dashboard analytics and reporting
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
import logging

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.account import Account
from app.models.cost_tracking import CostTracking
from app.schemas.common import DashboardStatsResponse
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get overall dashboard statistics
    - Total accounts created
    - Total jobs
    - Success rates by platform
    - Monthly cost
    - Active workers
    - Queue length
    """
    # Total accounts
    total_accounts_result = await db.execute(
        select(func.count()).select_from(Account)
        .join(Job).where(Job.user_id == current_user.id)
    )
    total_accounts = total_accounts_result.scalar()
    
    # Total jobs
    total_jobs_result = await db.execute(
        select(func.count()).select_from(Job).where(Job.user_id == current_user.id)
    )
    total_jobs = total_jobs_result.scalar()
    
    # Discord success rate
    discord_success_result = await db.execute(
        select(func.count()).select_from(Account)
        .join(Job).where(
            and_(
                Job.user_id == current_user.id,
                Account.platform == "discord",
                Account.status == "success"
            )
        )
    )
    discord_success = discord_success_result.scalar()
    
    discord_total_result = await db.execute(
        select(func.count()).select_from(Account)
        .join(Job).where(
            and_(
                Job.user_id == current_user.id,
                Account.platform == "discord"
            )
        )
    )
    discord_total = discord_total_result.scalar()
    
    discord_success_rate = (discord_success / discord_total) if discord_total > 0 else 0.0
    
    # Gmail success rate
    gmail_success_result = await db.execute(
        select(func.count()).select_from(Account)
        .join(Job).where(
            and_(
                Job.user_id == current_user.id,
                Account.platform == "gmail",
                Account.status == "success"
            )
        )
    )
    gmail_success = gmail_success_result.scalar()
    
    gmail_total_result = await db.execute(
        select(func.count()).select_from(Account)
        .join(Job).where(
            and_(
                Job.user_id == current_user.id,
                Account.platform == "gmail"
            )
        )
    )
    gmail_total = gmail_total_result.scalar()
    
    gmail_success_rate = (gmail_success / gmail_total) if gmail_total > 0 else 0.0
    
    # Monthly cost (current month)
    first_day_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    monthly_cost_result = await db.execute(
        select(func.sum(CostTracking.total_cost)).select_from(CostTracking)
        .join(Job).where(
            and_(
                Job.user_id == current_user.id,
                CostTracking.created_at >= first_day_of_month
            )
        )
    )
    monthly_cost = monthly_cost_result.scalar() or 0.0
    
    # Active workers (from Celery)
    try:
        from app.workers.celery_app import celery_app
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        active_workers = len(stats) if stats else 0
    except Exception as e:
        logger.error(f"Failed to get active workers: {e}")
        active_workers = 0
    
    # Queue length (from Celery)
    try:
        from app.workers.celery_app import celery_app
        inspect = celery_app.control.inspect()
        reserved = inspect.reserved()
        queue_length = sum(len(tasks) for tasks in reserved.values()) if reserved else 0
    except Exception as e:
        logger.error(f"Failed to get queue length: {e}")
        queue_length = 0
    
    return DashboardStatsResponse(
        total_accounts=total_accounts,
        total_jobs=total_jobs,
        discord_success_rate=round(discord_success_rate, 4),
        gmail_success_rate=round(gmail_success_rate, 4),
        monthly_cost=round(float(monthly_cost), 2),
        active_workers=active_workers,
        queue_length=queue_length
    )
