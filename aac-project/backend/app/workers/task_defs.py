"""
Main Celery tasks for account creation
Orchestrates Discord and Gmail automation workflows
"""
from __future__ import annotations

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio
import logging
import uuid

from app.workers.celery_app import celery_app
from app.core.database import async_session_maker
from app.models.job import Job
from app.models.cost_tracking import CostTracking
from app.services.proxy_service import ProxyService
from app.services.discord_service import create_discord_account_workflow
from app.services.gmail_service import create_gmail_account_workflow
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session"""
    _session = None

    @property
    def session(self):
        if self._session is None:
            self._session = async_session_maker()
        return self._session


@celery_app.task(bind=True, base=DatabaseTask, max_retries=3, default_retry_delay=60)
def create_accounts_task(
    self,
    job_id: str,
    platform: str,
    total_count: int,
    proxy_provider: str,
    sms_provider: str,
    captcha_provider: str,
    resume_from_index: int = 0
):
    """
    Main task for creating multiple accounts
    - Orchestrates the entire workflow
    - Handles retries with exponential backoff
    - Updates job progress in real-time
    """
    try:
        return asyncio.run(
            _create_accounts_async(
                job_id=job_id,
                platform=platform,
                total_count=total_count,
                proxy_provider=proxy_provider,
                sms_provider=sms_provider,
                captcha_provider=captcha_provider,
                resume_from_index=resume_from_index
            )
        )
    except Exception as exc:
        logger.error(f"Task failed for job {job_id}: {exc}", exc_info=True)

        # Update job status to failed
        asyncio.run(_update_job_status(job_id, "failed"))

        # Retry with exponential backoff
        countdown = 60 * (2 ** self.request.retries)  # 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=countdown)


async def _create_accounts_async(
    job_id: str,
    platform: str,
    total_count: int,
    proxy_provider: str,
    sms_provider: str,
    captcha_provider: str,
    resume_from_index: int = 0
):
    """
    Async implementation of account creation
    """
    async with async_session_maker() as db:
        # Get job
        result = await db.execute(
            select(Job).where(Job.id == uuid.UUID(job_id))
        )
        job = result.scalar_one_or_none()

        if not job:
            logger.error(f"Job {job_id} not found")
            return {"error": "Job not found"}

        # Update job status to running
        job.status = "running"
        await db.commit()

        logger.info(f"Starting job {job_id}: {platform} x {total_count}")

        # Initialize services
        proxy_service = ProxyService(db)

        # Track costs
        total_proxy_cost = 0.0
        total_sms_cost = 0.0
        total_captcha_cost = 0.0

        # Create accounts
        for i in range(resume_from_index, total_count):
            try:
                logger.info(f"Job {job_id}: Creating account {i+1}/{total_count}")

                # Get proxy
                proxy = await proxy_service.get_next_proxy(proxy_provider)
                if not proxy:
                    logger.error(f"No available proxy from {proxy_provider}")
                    job.failed_count += 1
                    continue

                # Create account based on platform
                if platform == "discord":
                    result = await create_discord_account_workflow(
                        db=db,
                        job_id=uuid.UUID(job_id),
                        proxy=proxy,
                        captcha_provider=captcha_provider
                    )
                elif platform == "gmail":
                    result = await create_gmail_account_workflow(
                        db=db,
                        job_id=uuid.UUID(job_id),
                        proxy=proxy,
                        sms_provider=sms_provider,
                        captcha_provider=captcha_provider
                    )
                else:
                    logger.error(f"Unknown platform: {platform}")
                    job.failed_count += 1
                    continue

                # Update job progress
                if result.get("success"):
                    job.success_count += 1
                    job.last_successful_index = i + 1

                    # Track costs
                    total_proxy_cost += result.get("proxy_cost", 0.0)
                    total_sms_cost += result.get("sms_cost", 0.0)
                    total_captcha_cost += result.get("captcha_cost", 0.0)

                    # Update proxy success
                    await proxy_service.record_proxy_success(proxy.id)
                else:
                    job.failed_count += 1
                    # Update proxy failure
                    await proxy_service.record_proxy_failure(proxy.id)

                await db.commit()

                # Small delay between accounts
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Failed to create account {i+1} for job {job_id}: {e}", exc_info=True)
                job.failed_count += 1
                await db.commit()
                continue

        # Save cost tracking
        cost_tracking = CostTracking(
            job_id=uuid.UUID(job_id),
            proxy_cost=total_proxy_cost,
            sms_cost=total_sms_cost,
            captcha_cost=total_captcha_cost,
            total_cost=total_proxy_cost + total_sms_cost + total_captcha_cost
        )
        db.add(cost_tracking)

        # Update job status
        job.status = "done"
        job.finished_at = datetime.utcnow()
        job.estimated_cost = cost_tracking.total_cost
        await db.commit()

        logger.info(f"Job {job_id} completed: {job.success_count} success, {job.failed_count} failed")

        return {
            "job_id": job_id,
            "success_count": job.success_count,
            "failed_count": job.failed_count,
            "total_cost": float(cost_tracking.total_cost)
        }


async def _update_job_status(job_id: str, status: str):
    """Helper to update job status"""
    async with async_session_maker() as db:
        result = await db.execute(
            select(Job).where(Job.id == uuid.UUID(job_id))
        )
        job = result.scalar_one_or_none()

        if job:
            job.status = status
            if status in ["done", "failed", "cancelled"]:
                job.finished_at = datetime.utcnow()
            await db.commit()


@celery_app.task
def health_check_proxies_task():
    """
    Periodic task to check proxy health
    Runs every 5 minutes
    """
    return asyncio.run(_health_check_proxies_async())


async def _health_check_proxies_async():
    """Async implementation of proxy health check"""
    from app.services.proxy_service import ProxyService

    async with async_session_maker() as db:
        proxy_service = ProxyService(db)
        checked_count = await proxy_service.health_check_all_proxies()
        logger.info(f"Health checked {checked_count} proxies")
        return {"checked": checked_count}


@celery_app.task
def cleanup_old_logs_task():
    """
    Periodic task to clean up old logs
    Runs daily
    """
    return asyncio.run(_cleanup_old_logs_async())


async def _cleanup_old_logs_async():
    """Async implementation of log cleanup"""
    from sqlalchemy import delete
    from app.models.log import Log
    from datetime import timedelta
    from app.core.config import settings

    async with async_session_maker() as db:
        cutoff_date = datetime.utcnow() - timedelta(days=settings.LOG_RETENTION_DAYS)

        result = await db.execute(
            delete(Log).where(Log.created_at < cutoff_date)
        )

        deleted_count = result.rowcount
        await db.commit()

        logger.info(f"Cleaned up {deleted_count} old logs")
        return {"deleted": deleted_count}


# Celery beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'health-check-proxies': {
        'task': 'app.workers.task_defs.health_check_proxies_task',
        'schedule': 300.0,  # 5 minutes
    },
    'cleanup-old-logs': {
        'task': 'app.workers.task_defs.cleanup_old_logs_task',
        'schedule': 86400.0,  # 24 hours
    },
}
