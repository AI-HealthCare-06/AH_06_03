"""서비스 안 공지 (약관 변경, 점검, 서비스 종료 안내 등). 이용약관의 "약관 변경·서비스 종료는 서비스 안에서 공지"를 지키기 위한 표.

공지는 모두에게 공개되는 내용이라 사용자 정보를 담지 않는다. 배너로 보여 주는 화면은 이 표를 읽기만 한다.
"""
from datetime import datetime

from sqlalchemy import CHAR, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class Notice(Base):
    __tablename__ = "notices"

    notice_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)   # 보이기 시작하는 시각 (UTC)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)           # 보이기를 끝내는 시각 (UTC), 없으면 계속
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)                # 쓴 관리자 이메일
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
