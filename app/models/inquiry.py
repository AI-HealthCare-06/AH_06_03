"""1:1 문의: 이용자가 문의를 남기면 운영팀이 서비스 안에서 답한다 (건강정보가 들어갈 수 있어 외부 메일을 쓰지 않는다).

user_id 칸이 있어서 회원 탈퇴 때 함께 지워진다. 건강정보 동의 철회로는 지우지 않는다(건강기록이 아니라 문의라서).
"""
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class Inquiry(Base):
    __tablename__ = "inquiries"

    inquiry_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)   # UTC
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_by: Mapped[str | None] = mapped_column(String(255), nullable=True)           # 답한 관리자 이메일
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user_read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)        # 이용자가 답변을 열어 본 시각
