import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token: Mapped[str | None] = mapped_column(Text, nullable=True)
    proxy_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sms_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    job: Mapped["Job"] = relationship("Job", back_populates="accounts")
    logs: Mapped[list["Log"]] = relationship("Log", back_populates="account", cascade="all, delete-orphan")
    proxy_usage: Mapped[list["ProxyUsage"]] = relationship("ProxyUsage", back_populates="account", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_accounts_job_id", "job_id"),
        Index("idx_accounts_platform", "platform"),
        Index("idx_accounts_status", "status"),
        Index("idx_accounts_email", "email"),
    )

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, platform='{self.platform}', email='{self.email}', status='{self.status}')>"