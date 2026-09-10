from datetime import datetime
import uuid
from sqlalchemy import Integer, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class ProxyUsage(Base):
    __tablename__ = "proxy_usage"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    proxy_id: Mapped[int | None] = mapped_column(ForeignKey("proxies.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    proxy: Mapped[Optional["Proxy"]] = relationship("Proxy")
    job: Mapped[Optional["Job"]] = relationship("Job")
    account: Mapped[Optional["Account"]] = relationship("Account", back_populates="proxy_usage")

    __table_args__ = (
        Index("idx_proxy_usage_proxy_id", "proxy_id"),
        Index("idx_proxy_usage_job_id", "job_id"),
        Index("idx_proxy_usage_account_id", "account_id"),
        Index("idx_proxy_usage_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ProxyUsage(id={self.id}, proxy_id={self.proxy_id}, success={self.success})>"