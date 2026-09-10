"""
Jobs API endpoints
Handles job creation, management, and monitoring
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional
from datetime import datetime
import logging
import uuid

from app.core.database import get_db
from app.core.auth import get_current_user, require_role
from app.models.user import User
from app.models.job import Job
from app.models.audit_log import AuditLog
from app.schemas.job import (
    JobCreate, JobResponse, JobListResponse,
    JobDetailResponse, JobStatus
)
from app.workers.tasks import create_accounts_task

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: Request,
    job_data: JobCreate,
    current_user: User = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new job for bulk account creation
    - Validates input parameters
    - Creates job record
    - Queues Celery task
    - Returns job ID for tracking
    """
    # Validate count
    if job_data.total_count < 1 or job_data.total_count > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="total_count must be between 1 and 1000"
        )
    
    # Validate platform
    if job_data.platform not in ["discord", "gmail"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="platform must be 'discord' or 'gmail'"
        )
    
    # Create job
    job = Job(
        id=uuid.uuid4(),
        user_id=current_user.id,
        type=job_data.platform,
        total_count=job_data.total_count,
        status=JobStatus.PENDING,
        proxy_provider=job_data.proxy_provider or "brightdata",
        sms_provider=job_data.sms_provider or "5sim",
        captcha_provider=job_data.captcha_provider or "2captcha"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Queue Celery task
    try:
        task = create_accounts_task.delay(
            job_id=str(job.id),
            platform=job_data.platform,
            total_count=job_data.total_count,
            proxy_provider=job.proxy_provider,
            sms_provider=job.sms_provider,
            captcha_provider=job.captcha_provider
        )
        
        logger.info(f"Job {job.id} queued with task ID {task.id}")
    except Exception as e:
        logger.error(f"Failed to queue job {job.id}: {e}")
        job.status = JobStatus.FAILED
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue job: {str(e)}"
        )
    
    # Log action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="create_job",
        resource_type="job",
        resource_id=str(job.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="success",
        details={
            "platform": job_data.platform,
            "total_count": job_data.total_count
        }
    )
    db.add(audit_log)
    await db.commit()
    
    return JobResponse(
        id=job.id,
        status=job.status,
        total_count=job.total_count,
        created_at=job.created_at
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    platform: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all jobs with optional filters
    - Supports pagination
    - Filters by status, platform
    - Returns job summary
    """
    # Build query
    query = select(Job).where(Job.user_id == current_user.id)
    
    if status_filter:
        query = query.where(Job.status == status_filter)
    
    if platform:
        query = query.where(Job.type == platform)
    
    # Count total
    count_query = select(func.count()).select_from(Job).where(Job.user_id == current_user.id)
    if status_filter:
        count_query = count_query.where(Job.status == status_filter)
    if platform:
        count_query = count_query.where(Job.type == platform)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Paginate
    query = query.order_by(Job.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    return JobListResponse(
        jobs=[
            JobResponse(
                id=job.id,
                status=job.status,
                total_count=job.total_count,
                created_at=job.created_at
            ) for job in jobs
        ],
        total=total,
        page=page,
        limit=limit
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific job
    """
    result = await db.execute(
        select(Job).where(and_(Job.id == job_id, Job.user_id == current_user.id))
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return JobDetailResponse(
        id=job.id,
        user_id=job.user_id,
        type=job.type,
        total_count=job.total_count,
        success_count=job.success_count,
        failed_count=job.failed_count,
        cancelled_count=job.cancelled_count,
        status=job.status,
        proxy_provider=job.proxy_provider,
        sms_provider=job.sms_provider,
        captcha_provider=job.captcha_provider,
        last_successful_index=job.last_successful_index,
        created_at=job.created_at,
        finished_at=job.finished_at,
        estimated_cost=float(job.estimated_cost) if job.estimated_cost else 0.0
    )


@router.post("/{job_id}/cancel")
async def cancel_job(
    request: Request,
    job_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel a running job
    - Stops Celery task
    - Updates job status
    - Preserves successfully created accounts
    """
    result = await db.execute(
        select(Job).where(and_(Job.id == job_id, Job.user_id == current_user.id))
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status {job.status}"
        )
    
    # Revoke Celery task
    try:
        from app.workers.celery_app import celery_app
        celery_app.control.revoke(str(job.id), terminate=True)
        logger.info(f"Revoked Celery task for job {job.id}")
    except Exception as e:
        logger.error(f"Failed to revoke task for job {job.id}: {e}")
    
    # Update job status
    job.status = JobStatus.CANCELLED
    job.finished_at = datetime.utcnow()
    await db.commit()
    
    # Log action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="cancel_job",
        resource_type="job",
        resource_id=str(job.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="success",
        details={"job_id": str(job.id)}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"id": job.id, "status": job.status}


@router.post("/{job_id}/resume")
async def resume_job(
    request: Request,
    job_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Resume a failed job from last successful state
    - Only for admin users
    - Continues from last_successful_index
    """
    result = await db.execute(
        select(Job).where(and_(Job.id == job_id, Job.user_id == current_user.id))
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume job with status {job.status}"
        )
    
    # Calculate remaining count
    remaining_count = job.total_count - job.last_successful_index
    
    if remaining_count <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job already completed all accounts"
        )
    
    # Update job status
    job.status = JobStatus.RUNNING
    await db.commit()
    
    # Queue new Celery task with resume index
    try:
        task = create_accounts_task.delay(
            job_id=str(job.id),
            platform=job.type,
            total_count=remaining_count,
            proxy_provider=job.proxy_provider,
            sms_provider=job.sms_provider,
            captcha_provider=job.captcha_provider,
            resume_from_index=job.last_successful_index
        )
        
        logger.info(f"Job {job.id} resumed from index {job.last_successful_index} with task ID {task.id}")
    except Exception as e:
        logger.error(f"Failed to resume job {job.id}: {e}")
        job.status = JobStatus.FAILED
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume job: {str(e)}"
        )
    
    # Log action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="resume_job",
        resource_type="job",
        resource_id=str(job.id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="success",
        details={"job_id": str(job.id), "resumed_from_index": job.last_successful_index}
    )
    db.add(audit_log)
    await db.commit()
    
    return {"id": job.id, "status": job.status, "resumed_from_index": job.last_successful_index}
