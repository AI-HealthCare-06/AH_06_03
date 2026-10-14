"""비회원 문의: 로그인·가입이 안 될 때 로그인 없이 남기는 문의. 이메일을 받지 않고, 문의를 보낼 때 알려 주는 조회 번호로 답변을 본다.

조회 번호와 IP는 원문이 아니라 해시로만 저장한다 (DB가 유출돼도 번호를 알 수 없고, IP는 횟수 제한에만 쓴다).
접수 30일이 지나면 새 문의가 들어올 때 함께 삭제한다.
"""
from datetime import datetime

from sqlalchemy import CHAR, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class GuestInquiry(Base):
    __tablename__ = "guest_inquiries"

    guest_inquiry_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    code_hash: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)    # 조회 번호의 해시
    ip_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False, index=True)       # 횟수 제한용 IP 해시
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)   # UTC
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
