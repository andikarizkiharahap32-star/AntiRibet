from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import String, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="logs")
    account: Mapped[Optional["Account"]] = relationship("Account", back_populates="logs")

    __table_args__ = (
        Index("idx_logs_job_id", "job_id"),
        Index("idx_logs_level", "level"),
        Index("idx_logs_created_at", "created_at"),
        Index("idx_logs_account_id", "account_id"),
    )

    def __repr__(self) -> str:
        return f"<Log(id={self.id}, level='{self.level}', job_id={self.job_id})>"