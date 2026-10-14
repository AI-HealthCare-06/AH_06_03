"""파이(포인트) 장부. 잔액은 따로 저장하지 않고 장부의 합계로 계산한다.

같은 일로 두 번 적립되지 않게 (회원, 이유, 기준 번호)를 하나로 묶는다.
회원 탈퇴 때는 user_id 칸이 있는 표라서 함께 지워진다. 건강정보가 아니라서 동의 철회로는 지우지 않는다.
"""
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class PieLedger(Base):
    __tablename__ = "pie_ledger"
    __table_args__ = (UniqueConstraint("user_id", "reason", "ref_key"),)

    entry_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)          # 적립은 +, 사용은 -
    reason: Mapped[str] = mapped_column(String(40), nullable=False)      # welcome, post_write, common_challenge_rank ...
    ref_key: Mapped[str] = mapped_column(String(80), nullable=False)     # 글 번호, 챌린지 번호처럼 "무엇 때문에"를 가리키는 값
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)   # UTC
