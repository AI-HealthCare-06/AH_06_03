"""회원 탈퇴 요청 기록 (ERD v8 account_deletion_requests). 지운 도메인별 개수는 result_summary에 남긴다."""
from datetime import datetime

from sqlalchemy import CHAR, JSON, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class AccountDeletionRequest(Base):
    __tablename__ = "account_deletion_requests"

    deletion_request_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.user_id"), nullable=False, index=True)
    reauthenticated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("requested", "processing", "completed", "failed", name="deletion_status"), nullable=False, default="requested"
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
