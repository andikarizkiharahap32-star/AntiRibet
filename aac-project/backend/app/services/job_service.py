import uuid
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobCreate, JobUpdate
import logging

logger = logging.getLogger(__name__)


class JobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(self, user_id: uuid.UUID, job_data: JobCreate) -> Job:
        job = Job(
            user_id=user_id,
            type=job_data.type,
            total_count=job_data.total_count,
            proxy_provider=job_data.proxy_provider,
            sms_provider=job_data.sms_provider,
            captcha_provider=job_data.captcha_provider,
            status="pending"
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_job(self, job_id: uuid.UUID) -> Optional[Job]:
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    async def get_jobs(
        self,
        user_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        type: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> tuple[List[Job], int]:
        query = select(Job)
        count_query = select(func.count(Job.id))

        if user_id:
            query = query.where(Job.user_id == user_id)
            count_query = count_query.where(Job.user_id == user_id)
        if status:
            query = query.where(Job.status == status)
            count_query = count_query.where(Job.status == status)
        if type:
            query = query.where(Job.type == type)
            count_query = count_query.where(Job.type == type)

        query = query.order_by(Job.created_at.desc())
        query = query.limit(limit).offset((page - 1) * limit)

        jobs_result = await self.db.execute(query)
        jobs = list(jobs_result.scalars().all())

        total = await self.db.scalar(count_query) or 0

        return jobs, total

    async def update_job(self, job_id: uuid.UUID, update_data: JobUpdate) -> Optional[Job]:
        job = await self.get_job(job_id)
        if not job:
            return None

        if update_data.status:
            job.status = update_data.status
            if update_data.status in ["done", "failed", "cancelled"]:
                from datetime import datetime
                job.finished_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def cancel_job(self, job_id: uuid.UUID) -> Optional[Job]:
        job = await self.get_job(job_id)
        if not job:
            return None

        if job.status == "running":
            job.status = "cancelled"
            from datetime import datetime
            job.finished_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(job)

        return job

    async def resume_job(self, job_id: uuid.UUID) -> Optional[Job]:
        job = await self.get_job(job_id)
        if not job or job.status != "failed":
            return None

        job.status = "running"
        job.last_successful_index = job.success_count
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def increment_counts(self, job_id: uuid.UUID, success: bool = True) -> Optional[Job]:
        job = await self.get_job(job_id)
        if not job:
            return None

        if success:
            job.success_count += 1
        else:
            job.failed_count += 1

        job.last_successful_index = job.success_count

        if job.success_count + job.failed_count >= job.total_count:
            job.status = "done"
            from datetime import datetime
            job.finished_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_job_stats(self) -> dict:
        total = await self.db.scalar(select(func.count(Job.id))) or 0
        running = await self.db.scalar(select(func.count(Job.id)).where(Job.status == "running")) or 0
        done = await self.db.scalar(select(func.count(Job.id)).where(Job.status == "done")) or 0
        failed = await self.db.scalar(select(func.count(Job.id)).where(Job.status == "failed")) or 0

        discord_total = await self.db.scalar(
            select(func.sum(Job.total_count)).where(Job.type == "discord")
        ) or 0
        discord_success = await self.db.scalar(
            select(func.sum(Job.success_count)).where(Job.type == "discord")
        ) or 0
        gmail_total = await self.db.scalar(
            select(func.sum(Job.total_count)).where(Job.type == "gmail")
        ) or 0
        gmail_success = await self.db.scalar(
            select(func.sum(Job.success_count)).where(Job.type == "gmail")
        ) or 0

        return {
            "total_jobs": total,
            "running_jobs": running,
            "completed_jobs": done,
            "failed_jobs": failed,
            "total_accounts_created": discord_success + gmail_success,
            "discord_success_rate": round(discord_success / discord_total, 4) if discord_total else 0.0,
            "gmail_success_rate": round(gmail_success / gmail_total, 4) if gmail_total else 0.0,
        }