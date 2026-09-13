import uuid
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.account import Account
from app.models.job import Job
from app.models.user import User
from app.core.security import encrypt_password, decrypt_password, get_password_hash
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class AccountService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_cli_user(self) -> User:
        """Ensure a system user exists for CLI-created jobs (non-null FK)."""
        result = await self.db.execute(
            select(User).where(User.username == settings.CLI_SYSTEM_USERNAME)
        )
        user = result.scalar_one_or_none()

        if user:
            return user

        user = User(
            username=settings.CLI_SYSTEM_USERNAME,
            password_hash=get_password_hash(settings.CLI_SYSTEM_PASSWORD),
            role=settings.CLI_SYSTEM_ROLE,
            is_active=True,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        logger.info(f"Created CLI system user: {user.username}")
        return user

    async def create_account(
        self,
        job_id: uuid.UUID,
        platform: str,
        email: str,
        username: str,
        password: str,
        token: Optional[str] = None,
        proxy_used: Optional[str] = None,
        sms_number: Optional[str] = None
    ) -> Account:
        account = Account(
            job_id=job_id,
            platform=platform,
            email=email,
            username=username,
            password_encrypted=encrypt_password(password),
            token=token,
            proxy_used=proxy_used,
            sms_number=sms_number,
            status="success"
        )
        self.db.add(account)
        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def get_account(self, account_id: uuid.UUID) -> Optional[Account]:
        result = await self.db.execute(select(Account).where(Account.id == account_id))
        return result.scalar_one_or_none()

    async def get_accounts(
        self,
        job_id: Optional[uuid.UUID] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 50
    ) -> tuple[List[Account], int]:
        query = select(Account)
        count_query = select(func.count(Account.id))

        if job_id:
            query = query.where(Account.job_id == job_id)
            count_query = count_query.where(Account.job_id == job_id)
        if platform:
            query = query.where(Account.platform == platform)
            count_query = count_query.where(Account.platform == platform)
        if status:
            query = query.where(Account.status == status)
            count_query = count_query.where(Account.status == status)

        query = query.order_by(Account.created_at.desc())
        query = query.limit(limit).offset((page - 1) * limit)

        accounts_result = await self.db.execute(query)
        accounts = list(accounts_result.scalars().all())

        total = await self.db.scalar(count_query) or 0

        return accounts, total

    async def update_account_status(
        self,
        account_id: uuid.UUID,
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[Account]:
        account = await self.get_account(account_id)
        if not account:
            return None

        account.status = status
        if error_message:
            account.error_message = error_message

        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def export_accounts(
        self,
        platform: Optional[str] = None,
        job_id: Optional[uuid.UUID] = None,
        include_password: bool = True
    ) -> List[dict]:
        query = select(Account)
        if platform:
            query = query.where(Account.platform == platform)
        if job_id:
            query = query.where(Account.job_id == job_id)

        query = query.where(Account.status == "success")
        query = query.order_by(Account.created_at.desc())
        query = query.limit(10000)

        result = await self.db.execute(query)
        accounts = result.scalars().all()

        exported = []
        for acc in accounts:
            data = {
                "email": acc.email,
                "username": acc.username,
                "platform": acc.platform,
                "created_at": acc.created_at.isoformat(),
            }
            if include_password:
                data["password"] = decrypt_password(acc.password_encrypted)
            exported.append(data)

        return exported

    async def get_account_count(self, platform: Optional[str] = None) -> int:
        query = select(func.count(Account.id)).where(Account.status == "success")
        if platform:
            query = query.where(Account.platform == platform)
        return await self.db.scalar(query) or 0