"""대상 확인 답(나이대·관상동맥질환·응급 상황)을 회원당 한 줄 저장. 새 기기에서 로그인해도 다시 묻지 않기 위한 표."""
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base


class UserEligibility(Base):
    __tablename__ = "user_eligibility"

    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    age_band: Mapped[str] = mapped_column(Enum("in", "bOnly", "under19", name="eligibility_age_band"), nullable=False)
    chd: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)   # 협심증·심근경색 등 관상동맥질환 진단 여부
    emergency: Mapped[str] = mapped_column(Enum("no", "yes", "unsure", name="eligibility_emergency"), nullable=False, default="no")
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
