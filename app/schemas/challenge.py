"""챌린지 신청서와 결과지 양식."""
from datetime import date

from app.schemas.health import MeasurementItem

from pydantic import BaseModel, ConfigDict, Field


class AnswerOption(BaseModel):
    code: str
    label: str


class MissionCard(BaseModel):
    """W09·W10 미션 카드. 문구는 가이드 §4.1 그대로."""
    code: str
    category: str
    category_name: str
    name: str
    difficulty: str  # low / medium / high (화면: 하 / 중 / 상)
    weekly_target: int
    description: str
    evidence: str
    source: str
    notice: str | None
    question: str
    answers: list[AnswerOption]
    completed_before: bool = False  # 이전 사이클에서 완료 → 축하 + 이어서 하기


class FixedSlot(BaseModel):
    slot: int  # 1 = 흡연 칸, 2 = 음주 칸
    slot_label: str
    selection_type: str  # fixed / replacement
    mission: MissionCard | None  # 넣을 미션이 없으면 None ("지금 생활습관이 잘 유지되고 있어요")


class ExcludedItem(BaseModel):
    code: str | None = None
    category: str
    name: str
    reason: str


class SurveyNeeded(BaseModel):
    category: str
    category_name: str


class SodiumResult(BaseModel):
    sodium_grade: str  # careful_low ~ severe / not_applicable
    sodium_est_mg: int | None = None
    sodium_index: float | None = None


class RecommendationResult(BaseModel):
    cycle_number: int  # 이번에 시작할 사이클 번호
    total_cycles: int
    fixed: list[FixedSlot]
    candidates: list[MissionCard]
    keep_going_message: str | None  # 완료한 미션이 있을 때 카드에 함께 표시
    excluded: list[ExcludedItem]
    survey_needed: list[SurveyNeeded]
    all_good: bool
    selectable_notice: str
    sodium: SodiumResult | None


class CycleStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_code: str


class LogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str | None = None
    quantity: float | None = None
    note: str | None = Field(default=None, max_length=500)


class LogResult(BaseModel):
    log_date: date
    status: str  # completed / failed / skipped
    answer: str | None
    quantity: float | None
    limit_exceeded: bool
    warning: str | None = None  # 절주 초과 경고 (REQ-CHAL-010)


class WeekProgress(BaseModel):
    week: int
    completed: int
    target: int
    rate: float


class CycleMission(BaseModel):
    cycle_challenge_id: str
    selection_type: str
    status: str
    card: MissionCard
    weekly_target: int
    target_config: dict | None
    weeks: list[WeekProgress]
    cycle_rate: float
    streak: int
    today_log: LogResult | None
    logs: list[LogResult]


class CycleResult(BaseModel):
    cycle_id: str
    cycle_number: int
    total_cycles: int
    status: str  # active / completed / incomplete / stopped
    started_on: date
    ended_on: date
    today: date
    day_number: int  # 1~28 (종료 후에는 28)
    week_number: int  # 1~4
    missions: list[CycleMission]


class CycleSummary(BaseModel):
    cycle_id: str
    cycle_number: int
    status: str
    started_on: date
    ended_on: date
    cycle_rate: float
    mission_codes: list[str]
    reassessed: bool  # 4주 재입력을 마쳤는가 (끝난 사이클에서 false면 재입력 안내)


class CycleStopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str | None = Field(default=None, max_length=30)
    note: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------- 4주 재입력·전후 비교 (가이드 §6, W11-2)
class ReassessmentRequest(BaseModel):
    """다시 받는 항목만 보낸다 (가이드 §6.1). 혈압은 두 번 잰 평균. 나머지는 직전 값을 서버가 가져온다."""
    model_config = ConfigDict(extra="forbid")

    examination_date: date | None = None  # 비우면 오늘
    measurements: list[MeasurementItem] = Field(min_length=1)


class Snapshot(BaseModel):
    examination_date: date
    sbp: float | None
    dbp: float | None
    weight_kg: float | None
    waist_cm: float | None
    smoking: str | None
    drink_freq: str | None
    drink_amount: str | None


class ModelChange(BaseModel):
    model_code: str
    before_status: str | None
    before_risk_level: str | None
    before_probability: float | None
    after_status: str | None
    after_risk_level: str | None
    after_probability: float | None
    model_version: str | None
    comparable: bool  # 둘 다 완료 + 같은 모델 버전일 때만 비교 표시 (NFR-ARCH-004)


class MissionResult(BaseModel):
    code: str
    name: str
    status: str
    cycle_rate: float


class ReviewResult(BaseModel):
    cycle_id: str
    cycle_number: int
    total_cycles: int
    cycle_status: str
    reassessed: bool
    before: Snapshot | None
    after: Snapshot | None
    missions: list[MissionResult]
    normal_weight_range: list[int] | None  # [하한, 상한] kg (키 기준 BMI 18.5~22.9)
    waist_limit: int
    models: list[ModelChange]
    bp_note: str
