"""건강정보 테이블 설계도. 기준: ERD v9 health_input_schemas, health_records, health_measurements"""
from datetime import date, datetime

from sqlalchemy import CHAR, Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id

class HealthInputSchema(Base):
    """입력 양식 버전 (REQ-HEALTH-002)."""
    __tablename__ = "health_input_schemas"

    health_schema_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    schema_version: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    model_scope: Mapped[str] = mapped_column(
        Enum("MODEL_A", "MODEL_B", "BOTH", "TRACKING", name="model_scope_type"), nullable=False
    )
    active_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class HealthRecord(Base):
    """검진·재평가·주간 혈압 기록 한 번 (상자)."""
    __tablename__ = "health_records"
    # 중복 금지 규칙
    __table_args__ = (UniqueConstraint("user_id", "input_type", "examination_date"),)

    health_record_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id"), nullable=False, index=True
    )
    health_schema_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("health_input_schemas.health_schema_id"), nullable=False
    )
    cycle_id: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)  # 챌린지 사이클 표가 생기면 연결
    input_type: Mapped[str] = mapped_column(
        Enum("initial", "interim_reassessment", "full_reassessment", "weekly_bp", "manual", name="health_input_type"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        Enum("manual", "ocr", "mixed", name="health_source_type"), nullable=False, default="manual"
    )
    examination_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class HealthMeasurement(Base):
    """측정값 하나 (상자 안의 물건)."""
    __tablename__ = "health_measurements"
    __table_args__ = (UniqueConstraint("health_record_id", "metric_code"),)

    measurement_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    health_record_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("health_records.health_record_id", ondelete="CASCADE"), nullable=False)
    metric_code: Mapped[str] = mapped_column(String(50), nullable=False)
    value_num: Mapped[float | None] = mapped_column(Numeric(12, 4, asdecimal=False), nullable=True)
    value_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    measured_on: Mapped[date] = mapped_column(Date, nullable=False)
    input_method: Mapped[str] = mapped_column(
        Enum("manual", "ocr", "calculated", "carried_forward", name="measurement_input_method"),
        nullable=False,
        default="manual",
    )
    source_measurement_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("health_measurements.measurement_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)