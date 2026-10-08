"""챌린지 테이블 설계도. 기준: ERD v8 challenge_categories, challenges, challenge_levels,
challenge_cycles, cycle_challenges, challenge_logs, user_classifications"""
from datetime import date, datetime

from sqlalchemy import (
    CHAR, JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id

DIFFICULTY = Enum("low", "medium", "high", name="difficulty_level")


class ChallengeCategory(Base):
    """카테고리 (금연·절주·나트륨·신체 활동·외식·아침·체중). 관리자가 노출·순서를 바꾼다."""
    __tablename__ = "challenge_categories"

    category_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    category_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Challenge(Base):
    """미션 하나 (SMK-1 등). 화면 문구는 app/services/challenge_catalog.py."""
    __tablename__ = "challenges"

    challenge_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    category_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("challenge_categories.category_id"), nullable=False
    )
    challenge_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    challenge_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    mission_role: Mapped[str] = mapped_column(
        Enum("fixed", "selectable", "replacement", name="mission_role_type"), nullable=False
    )
    proof_type: Mapped[str] = mapped_column(
        Enum("photo", "self_record", "automatic", "measurement", name="proof_type"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ChallengeLevel(Base):
    """미션별 난이도·주간 목표 (REQ-CHAL-004·009)."""
    __tablename__ = "challenge_levels"
    __table_args__ = (UniqueConstraint("challenge_id", "difficulty"),)

    challenge_level_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    challenge_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("challenges.challenge_id"), nullable=False)
    difficulty: Mapped[str] = mapped_column(DIFFICULTY, nullable=False)
    weekly_target: Mapped[int] = mapped_column(Integer, nullable=False)
    target_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ChallengeCycle(Base):
    """4주 사이클 한 번. 프로그램은 4사이클(16주)."""
    __tablename__ = "challenge_cycles"

    cycle_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1~4
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    ended_on: Mapped[date] = mapped_column(Date, nullable=False)  # started_on + 27일
    status: Mapped[str] = mapped_column(
        Enum("active", "completed", "incomplete", "stopped", name="cycle_status"), nullable=False, default="active"
    )
    stopped_reason_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    stopped_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CycleChallenge(Base):
    """사이클에 들어간 미션 (고정 2 + 선택 1). 시작 시점 목표를 스냅샷으로 저장."""
    __tablename__ = "cycle_challenges"
    __table_args__ = (UniqueConstraint("cycle_id", "challenge_id"),)

    cycle_challenge_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    cycle_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("challenge_cycles.cycle_id", ondelete="CASCADE"), nullable=False, index=True
    )
    challenge_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("challenges.challenge_id"), nullable=False)
    selection_type: Mapped[str] = mapped_column(
        Enum("fixed", "replacement", "selected", name="selection_type"), nullable=False
    )
    difficulty: Mapped[str] = mapped_column(DIFFICULTY, nullable=False)
    weekly_target: Mapped[int] = mapped_column(Integer, nullable=False)
    target_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("active", "completed", "incomplete", "stopped", name="cycle_challenge_status"),
        nullable=False, default="active",
    )


class ChallengeLog(Base):
    """매일 기록. 미션·날짜당 1건, 당일만 수정 (REQ-CHAL-004·005·010)."""
    __tablename__ = "challenge_logs"
    __table_args__ = (UniqueConstraint("cycle_challenge_id", "log_date"),)

    challenge_log_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    cycle_challenge_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("cycle_challenges.cycle_challenge_id", ondelete="CASCADE"), nullable=False
    )
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("completed", "failed", "skipped", name="challenge_log_status"), nullable=False
    )
    answer: Mapped[str | None] = mapped_column(String(30), nullable=True)  # 화면에서 고른 선택지 코드
    quantity: Mapped[float | None] = mapped_column(Numeric(8, 2, asdecimal=False), nullable=True)
    limit_exceeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class UserClassification(Base):
    """챌린지 판정에 쓴 분류 (가이드 §2.2). 사이클을 시작할 때 그때 값으로 저장."""
    __tablename__ = "user_classifications"
    __table_args__ = (UniqueConstraint("cycle_id", "classification_code"),)

    user_classification_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    cycle_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("challenge_cycles.cycle_id", ondelete="CASCADE"), nullable=False
    )
    survey_instance_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("survey_instances.survey_instance_id", ondelete="SET NULL"), nullable=True
    )
    health_record_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("health_records.health_record_id", ondelete="SET NULL"), nullable=True
    )
    classification_code: Mapped[str] = mapped_column(String(50), nullable=False)
    classification_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    classified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
