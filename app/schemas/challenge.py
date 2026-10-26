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
    kind: str  # doing_well(이미 잘함) / need_info(정보를 입력하면 추천) / not_advised(지금은 권하지 않음)
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
    autofilled: bool = False  # 체험 모드(DEMO_AUTOFILL)에서 3일치 기록으로 나머지 4주를 채웠다
    autofill_pattern: str | None = None  # 채운 패턴: steady(꾸준함) / wobble(중간에 흔들림) / fade(후반에 놓침, 판정은 미완료)


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


class DemoInfo(BaseModel):
    """체험(DEMO_AUTOFILL) 중 진행 중인 사이클의 상태. 체험이 꺼져 있으면 CycleResult.demo는 None."""
    record_days: int  # 기록한 날 수
    phase: str  # recording(기록 중) / finish_today(3번째 기록일: 오늘 마치고 결과 보기) / finish_only(3번째 기록일이 지남: 결과 보기만)
    unlogged_today: int  # 오늘 아직 기록하지 않은 미션 수


class DemoStatus(BaseModel):
    enabled: bool
    ended: bool  # 체험 마지막 날이 지났다
    ends_on: date | None
    has_result: bool  # 자동 채움으로 4주 결과를 받은 사이클이 있다


class DemoFinishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False  # 오늘 기록하지 않은 미션이 남아 있어도 마친다


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
    demo: DemoInfo | None = None


class CycleSummary(BaseModel):
    cycle_id: str
    cycle_number: int
    program_number: int
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
    reason: str | None = None  # 비교 못 하는 이유: missing / skipped / model_version_changed
    before_similarity_level: str | None = None
    after_similarity_level: str | None = None
    before_percentile: float | None = None     # 모델 A: 같은 성별·연령대 상위 N% (참고용)
    after_percentile: float | None = None


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
    demo_fill: str | None = None  # 체험 자동 채움 패턴(steady 꾸준함/wobble 중간에 흔들림/fade 후반에 놓침). 가상 기록이 섞인 사이클이면 값이 있다

class ProgramCheckpoint(Snapshot):
    """12주 중 한 시점의 측정값 (0주=처음 입력, 4·8·12주=각 사이클 끝 재입력)."""
    week: int


class ProgramCycleRate(BaseModel):
    cycle_number: int
    status: str
    cycle_rate: float           # 그 사이클 미션 달성률 (0~1)


class ProgramStatus(BaseModel):
    """가장 최근 12주 프로그램의 상태와 모델 버전 안내."""
    program_number: int
    complete: bool
    can_restart: bool

    # 프론트가 표시할 대표 모델(A) 버전
    model_version: str | None
    latest_model_version: str
    version_changed: bool
    latest_updated_on: date | None
    change_note: str | None

    # 서버 보관·검증용: 프론트는 몰라도 무시한다.
    model_a_version: str | None = None
    model_b_version: str | None = None


class ProgramReviewResult(BaseModel):
    """12주 프로그램의 처음(0주) ↔ 지금까지(마지막 재입력) 비교. 모델 결과는 같은 모델 버전으로 다시 계산한 값끼리 비교한다."""
    program_number: int
    model_version: str | None
    model_updated_on: date | None
    weeks_done: int
    before: Snapshot                     # 0주 (처음 입력)
    after: Snapshot                      # 12주 (3차 사이클 끝 재입력)
    checkpoints: list[ProgramCheckpoint]  # 혈압 선 그래프용 0·4·8·12주 (재입력이 없는 시점은 빠짐)
    cycles: list[ProgramCycleRate]       # 1·2·3차 달성률
    models: list[ModelChange]            # 모델 A·B 처음 ↔ 12주 (comparable=false면 reason으로 이유)
    bp_note: str