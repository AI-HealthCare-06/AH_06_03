"""건강기록 신청서와 결과지 양식."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InputType = Literal["initial", "interim_reassessment", "full_reassessment", "weekly_bp", "manual"]


class HealthRecordCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_type: InputType
    examination_date: date

class HealthRecordResult(BaseModel):
    health_record_id: str
    input_type: InputType
    examination_date: date

class MeasurementItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_code: str
    value_num: float | None = None
    value_code: str | None = None
    unit: str | None = None

class MeasurementsCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurements: list[MeasurementItem] = Field(min_length=1)

class MeasurementResult(BaseModel):
    measurement_id: str
    metric_code: str
    value_num: float | None
    value_code: str | None
    unit: str | None
    input_method: str

class HealthRecordDetail(BaseModel):
    """건강기록 상세: 상자 정보 + 안에 든 측정값 전부 (재로그인 복원·마이페이지용)."""
    health_record_id: str
    input_type: InputType
    examination_date: date
    measurements: list[MeasurementResult]
