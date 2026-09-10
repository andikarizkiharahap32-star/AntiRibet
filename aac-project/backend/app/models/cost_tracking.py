from datetime import datetime
from decimal import Decimal
import uuid
from sqlalchemy import DateTime, ForeignKey, DECIMAL, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class CostTracking(Base):
    __tablename__ = "cost_tracking"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    proxy_cost: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0.00, nullable=False)
    sms_cost: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0.00, nullable=False)
    captcha_cost: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0.00, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0.00, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="cost_tracking")

    __table_args__ = (
        Index("idx_cost_tracking_job_id", "job_id"),
        Index("idx_cost_tracking_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<CostTracking(id={self.id}, job_id={self.job_id}, total={self.total_cost})>"