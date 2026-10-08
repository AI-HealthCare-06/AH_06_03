"""생활습관 설문 테이블 설계도. 기준: ERD v9 (1차: 보기 하나만 고르는 설문)"""
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class SurveyVersion(Base):
    """📚 설문지 (문제지 맨 위층)."""
    __tablename__ = "survey_versions"
    __table_args__ = (UniqueConstraint("survey_type", "version"),)

    survey_version_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    survey_type: Mapped[str] = mapped_column(
        Enum("initial_lifestyle", "interim_lifestyle", "sodium", name="survey_type"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    active_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    active_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class SurveyQuestion(Base):
    """❓ 질문."""
    __tablename__ = "survey_questions"
    __table_args__ = (UniqueConstraint("survey_version_id", "question_code"),)

    question_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    survey_version_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("survey_versions.survey_version_id", ondelete="CASCADE"), nullable=False
    )
    question_code: Mapped[str] = mapped_column(String(50), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    answer_type: Mapped[str] = mapped_column(
        Enum("single_select", "number", name="survey_answer_type"),
        nullable=False, default="single_select", server_default="single_select",
    )
    num_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_max: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SurveyOption(Base):
    """🔘 보기."""
    __tablename__ = "survey_options"
    __table_args__ = (UniqueConstraint("question_id", "option_code"),)

    option_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    question_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("survey_questions.question_id", ondelete="CASCADE"), nullable=False
    )
    option_code: Mapped[str] = mapped_column(String(50), nullable=False)
    option_text: Mapped[str] = mapped_column(String(255), nullable=False)
    numeric_score: Mapped[float | None] = mapped_column(Numeric(8, 2, asdecimal=False), nullable=True)
    model_value_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

class SurveyInstance(Base):
    """📋 답안지 한 장."""
    __tablename__ = "survey_instances"

    survey_instance_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    survey_version_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("survey_versions.survey_version_id"), nullable=False
    )
    health_record_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("health_records.health_record_id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Enum("started", "submitted", "abandoned", name="survey_instance_status"),
        nullable=False,
        default="started",
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SurveyResponse(Base):
    """✔️ 답 하나."""
    __tablename__ = "survey_responses"
    __table_args__ = (UniqueConstraint("survey_instance_id", "question_id"),)

    response_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    survey_instance_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("survey_instances.survey_instance_id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("survey_questions.question_id"), nullable=False)
    option_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("survey_options.option_id"), nullable=True
    )
    value_num: Mapped[float | None] = mapped_column(Numeric(12, 4, asdecimal=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)