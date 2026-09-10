"""
Accounts API endpoints
Handles account listing and export
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional
import logging
import uuid
import csv
import json
import io

from app.core.database import get_db
from app.core.auth import get_current_user, require_role
from app.models.user import User
from app.models.account import Account
from app.models.job import Job
from app.models.audit_log import AuditLog
from app.schemas.account import AccountResponse, AccountListResponse
from app.core.config import settings
from app.services.account_service import decrypt_password

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=AccountListResponse)
async def list_accounts(
    platform: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    job_id: Optional[uuid.UUID] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List accounts with filters
    - Filters by platform, status, job_id
    - Supports pagination
    - Does not return decrypted passwords (use export endpoint)
    """
    # Build query - only show user's accounts
    query = select(Account).join(Job).where(Job.user_id == current_user.id)
    
    if platform:
        query = query.where(Account.platform == platform)
    
    if status_filter:
        query = query.where(Account.status == status_filter)
    
    if job_id:
        query = query.where(Account.job_id == job_id)
    
    # Count total
    count_query = select(func.count()).select_from(Account).join(Job).where(Job.user_id == current_user.id)
    if platform:
        count_query = count_query.where(Account.platform == platform)
    if status_filter:
        count_query = count_query.where(Account.status == status_filter)
    if job_id:
        count_query = count_query.where(Account.job_id == job_id)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Paginate
    query = query.order_by(Account.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)
    
    result = await db.execute(query)
    accounts = result.scalars().all()
    
    return AccountListResponse(
        accounts=[
            AccountResponse(
                id=account.id,
                job_id=account.job_id,
                platform=account.platform,
                email=account.email,
                username=account.username,
                status=account.status,
                proxy_used=account.proxy_used,
                created_at=account.created_at,
                # Don't include password in list view
                password=None,
                token=None
            ) for account in accounts
        ],
        total=total,
        page=page,
        limit=limit
    )


@router.get("/export")
async def export_accounts(
    request: Request,
    format: str = Query("csv", regex="^(csv|json)$"),
    platform: Optional[str] = Query(None),
    job_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(require_role(["admin", "operator"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Export accounts to CSV or JSON
    - Decrypts passwords for export
    - Filters by platform and job_id
    - Limits to EXPORT_MAX_RECORDS
    - Logs export action for audit
    """
    # Build query
    query = select(Account).join(Job).where(
        and_(
            Job.user_id == current_user.id,
            Account.status == "success"
        )
    )
    
    if platform:
        query = query.where(Account.platform == platform)
    
    if job_id:
        query = query.where(Account.job_id == job_id)
    
    # Limit to max records
    query = query.order_by(Account.created_at.desc()).limit(settings.EXPORT_MAX_RECORDS)
    
    result = await db.execute(query)
    accounts = result.scalars().all()
    
    if not accounts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No accounts found matching criteria"
        )
    
    # Decrypt passwords
    decrypted_accounts = []
    for account in accounts:
        try:
            password = decrypt_password(account.password_encrypted)
            decrypted_accounts.append({
                "id": str(account.id),
                "platform": account.platform,
                "email": account.email,
                "username": account.username,
                "password": password,
                "token": account.token,
                "proxy_used": account.proxy_used,
                "created_at": account.created_at.isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to decrypt password for account {account.id}: {e}")
            continue
    
    # Log export action
    audit_log = AuditLog(
        user_id=current_user.id,
        action="export",
        resource_type="account",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        status="success",
        details={
            "format": format,
            "platform": platform,
            "job_id": str(job_id) if job_id else None,
            "count": len(decrypted_accounts)
        }
    )
    db.add(audit_log)
    await db.commit()
    
    # Generate export file
    if format == "csv":
        output = io.StringIO()
        if decrypted_accounts:
            writer = csv.DictWriter(output, fieldnames=decrypted_accounts[0].keys())
            writer.writeheader()
            writer.writerows(decrypted_accounts)
        
        csv_content = output.getvalue()
        output.close()
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=accounts_{platform or 'all'}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
    
    else:  # json
        json_content = json.dumps(decrypted_accounts, indent=2)
        
        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=accounts_{platform or 'all'}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            }
        )


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed account information
    - Returns decrypted password (admin/operator only)
    """
    result = await db.execute(
        select(Account).join(Job).where(
            and_(
                Account.id == account_id,
                Job.user_id == current_user.id
            )
        )
    )
    account = result.scalar_one_or_none()
    
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    
    # Decrypt password if user has permission
    password = None
    if current_user.role in ["admin", "operator"]:
        try:
            password = decrypt_password(account.password_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt password for account {account.id}: {e}")
    
    return AccountResponse(
        id=account.id,
        job_id=account.job_id,
        platform=account.platform,
        email=account.email,
        username=account.username,
        password=password,
        token=account.token,
        status=account.status,
        proxy_used=account.proxy_used,
        created_at=account.created_at,
        error_message=account.error_message
    )


from datetime import datetime
