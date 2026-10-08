"""챌린지 신청서와 결과지 양식."""
from datetime import date

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


class CycleStopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str | None = Field(default=None, max_length=30)
    note: str | None = Field(default=None, max_length=500)
