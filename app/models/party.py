"""파티: 최대 6명, 한 사람에 한 파티, 초대 코드로 참여, 파티가 정한 챌린지 1개를 함께 인증.
파티 표에는 user_id 칸을 두지 않는다(파티장이 탈퇴·철회해도 파티는 남게).
파티원·인증 표에는 user_id가 있어서 탈퇴·건강정보 동의 철회 때 그 사람 것만 자동으로 빠진다.
파티장은 '가장 먼저 들어온 파티원'이다."""
from datetime import date, datetime

from sqlalchemy import CHAR, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id

MAX_MEMBERS = 6


class Party(Base):
    __tablename__ = "parties"

    party_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(12), nullable=False)
    intro: Mapped[str | None] = mapped_column(String(60), nullable=True)
    invite_code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)   # PAEON-7K3Q
    challenge_code: Mapped[str] = mapped_column(String(20), nullable=False)             # 파티가 함께 하는 미션 (예: NA-1)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)                      # 파티 시작일 (한국 날짜)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PartyMember(Base):
    __tablename__ = "party_members"
    __table_args__ = (UniqueConstraint("user_id", name="uq_party_members_user"),)   # 한 사람에 한 파티

    party_member_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    party_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("parties.party_id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    joined_on: Mapped[date] = mapped_column(Date, nullable=False)    # 들어온 날 (한국 날짜, "N일 중 M일"의 시작)


class PartyCheckin(Base):
    """파티 챌린지 인증 한 번 (한 사람이 하루에 한 번)."""
    __tablename__ = "party_checkins"
    __table_args__ = (UniqueConstraint("party_id", "user_id", "checkin_date", name="uq_party_checkins_day"),)

    party_checkin_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    party_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("parties.party_id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)   # 한국 날짜
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)