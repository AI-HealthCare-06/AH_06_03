"""공통 챌린지: 운영팀이 열고 전체 이용자가 함께하는 기간 한정 챌린지. 순위는 인증한 일수로만 정한다.

참여·인증 표에는 user_id 칸이 있어 탈퇴 때 함께 지워진다. 인증 때 받은 걸음 수는 인증 여부를 가리는 데만 쓰고,
순위나 목록에는 내보내지 않는다 (건강 수치를 서로 비교하지 않는다).
"""
from datetime import date, datetime

from sqlalchemy import CHAR, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class CommonChallenge(Base):
    __tablename__ = "common_challenges"

    challenge_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(60), nullable=False)
    proof_type: Mapped[str] = mapped_column(String(10), nullable=False)          # steps(걸음 수) / self(직접 인증)
    target_steps: Mapped[int | None] = mapped_column(Integer, nullable=True)     # steps일 때 하루 목표 걸음 수
    starts_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)    # 한국 날짜
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    complete_min_days: Mapped[int] = mapped_column(Integer, nullable=False)      # 이 일수 이상 인증하면 완주
    reward_first: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    reward_second: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    reward_third: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    reward_complete: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)   # 순위를 확정하고 보상을 준 시각
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)             # 만든 관리자 이메일
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CommonChallengeParticipant(Base):
    __tablename__ = "common_challenge_participants"
    __table_args__ = (UniqueConstraint("challenge_id", "user_id"),)

    participant_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    challenge_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("common_challenges.challenge_id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CommonChallengeCert(Base):
    """하루 한 번의 인증. 한국 날짜 기준으로 같은 날 두 번은 안 된다."""
    __tablename__ = "common_challenge_certs"
    __table_args__ = (UniqueConstraint("challenge_id", "user_id", "cert_date"),)

    cert_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    challenge_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("common_challenges.challenge_id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    cert_date: Mapped[date] = mapped_column(Date, nullable=False)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)   # UTC. 같은 일수일 때 먼저 도달한 사람을 가린다
