"""서비스 접속(로그인) 기록: 누가 언제 어느 IP에서 로그인했는지. 접속 기록 보관 기준(3개월)에 맞춰 보관한다.

탈퇴한 뒤에도 보관 기간 동안은 남겨야 하므로 칸 이름을 user_id가 아닌 account_id로 둔다
(탈퇴가 user_id 칸이 있는 표를 지우고, 내 데이터 내려받기가 그 표들을 담기 때문이다).
"""
from datetime import datetime

from sqlalchemy import CHAR, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class AccessLog(Base):
    __tablename__ = "access_logs"

    access_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    event: Mapped[str] = mapped_column(String(20), nullable=False)          # login
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)  # UTC
