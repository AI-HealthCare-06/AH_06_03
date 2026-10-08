"""예측 결과 테이블 설계도. 기준: ERD v9 (1차: 번호표·결과·요인 세 표)"""
from datetime import datetime

from sqlalchemy import CHAR, JSON, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class PredictionJob(Base):
    """🎫 번호표 (예측 신청 한 번)."""
    __tablename__ = "prediction_jobs"

    prediction_job_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    health_record_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("health_records.health_record_id", ondelete="CASCADE"), nullable=False
    )
    survey_instance_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("survey_instances.survey_instance_id", ondelete="SET NULL"), nullable=True
    )
    request_type: Mapped[str] = mapped_column(
        Enum("initial", "interim", "full", "manual", name="prediction_request_type"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum("queued", "running", "completed", "failed", name="prediction_job_status"),
        nullable=False,
        default="queued",
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 예측에 넣은 입력 그대로 (4주 재예측 때 나이를 처음 값으로 유지하는 데 씀). 마이그레이션 0e62093ddb61
    input_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Prediction(Base):
    """📊 모델별 결과 (번호표 하나에 모델 A·B 각각 한 줄)."""
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("prediction_job_id", "model_code"),)

    prediction_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    prediction_job_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("prediction_jobs.prediction_job_id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_code: Mapped[str] = mapped_column(Enum("MODEL_A", "MODEL_B", name="model_code"), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("completed", "skipped", "failed", name="prediction_status"), nullable=False
    )
    skip_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    score: Mapped[float | None] = mapped_column(Numeric(8, 6, asdecimal=False), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(
        Enum("normal", "borderline", "high", name="risk_level_type"), nullable=True
    )
    vascular_age: Mapped[float | None] = mapped_column(Numeric(5, 1, asdecimal=False), nullable=True)
    missing_features: Mapped[list | None] = mapped_column(JSON, nullable=True)
    predicted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)   

class PredictionFactor(Base):
    """🔹 요인 하나 (점수를 올리거나 내린 이유)."""
    __tablename__ = "prediction_factors"
    __table_args__ = (UniqueConstraint("prediction_id", "factor_code"),)

    prediction_factor_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    prediction_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("predictions.prediction_id", ondelete="CASCADE"), nullable=False
    )
    factor_code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    value_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    importance: Mapped[float] = mapped_column(Numeric(12, 8, asdecimal=False), nullable=False)
    direction: Mapped[str] = mapped_column(
        Enum("risk_increase", "protective", name="factor_direction"), nullable=False
    )
    modifiable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    direction_matches_expectation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    display_rank: Mapped[int] = mapped_column(Integer, nullable=False)