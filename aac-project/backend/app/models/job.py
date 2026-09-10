import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, Text, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cancelled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    proxy_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sms_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    captcha_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_successful_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    estimated_cost: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0.00, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="jobs")
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="job", cascade="all, delete-orphan")
    logs: Mapped[list["Log"]] = relationship("Log", back_populates="job", cascade="all, delete-orphan")
    cost_tracking: Mapped[list["CostTracking"]] = relationship("CostTracking", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_jobs_user_id", "user_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_type", "type"),
        Index("idx_jobs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, type='{self.type}', status='{self.status}', total={self.total_count})>"