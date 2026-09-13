from datetime import datetime
import uuid
from sqlalchemy import String, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user: Mapped["User | None"] = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action='{self.action}', status='{self.status}')>"