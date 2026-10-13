"""관리자 행위 기록 (REQ-ADM-005): 누가 언제 무엇을 보거나 바꿨는지 남긴다.

user_id 칸을 일부러 두지 않는다. 회원 탈퇴가 user_id 칸이 있는 표를 지우고, 내 데이터 내려받기가 그 표들을 담기 때문에,
관리자가 탈퇴해도 기록은 남아야 한다. 보는 사람을 알아볼 이메일만 남기고 사용자 개인정보는 담지 않는다.
"""
from datetime import datetime

from sqlalchemy import CHAR, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    audit_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)   # catalog_view, category_update ...
    target: Mapped[str | None] = mapped_column(String(100), nullable=True)   # 카테고리·미션 코드
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)   # 무엇이 어떻게 바뀌었는지
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)  # UTC
