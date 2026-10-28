"""관리자 운영 현황 입출력 양식: 진행 단계별 인원, 동의·삭제 현황, 서비스 상태. 숫자만 담고 사용자를 알아볼 값은 없다."""
from datetime import date, datetime

from pydantic import BaseModel


class FunnelStage(BaseModel):
    code: str
    label: str
    users: int                          # 그 단계까지 간 사용자 수
    rate_of_signup: float | None        # 가입 대비 비율
    rate_of_previous: float | None      # 앞 단계 대비 비율 (첫 단계는 None)


class ConsentCount(BaseModel):
    policy_type: str
    version: str
    agreed: int
    withdrawn: int


class DeletionEvent(BaseModel):
    completed_at: datetime | None       # UTC
    deleted_rows: int                   # 지운 기록 수의 합 (누구의 기록인지는 담지 않는다)


class DeletionStat(BaseModel):
    deleted_accounts: int
    consent_withdrawals: int
    recent: list[DeletionEvent]


class ServiceStatus(BaseModel):
    server_started_at: datetime         # UTC
    uptime_seconds: int
    db_ok: bool
    db_revision: str | None             # 마이그레이션 번호
    admin_count: int


class DailyActivity(BaseModel):
    """하루치 활동 집계 (한국 시각 기준 날짜). 사용자를 알아볼 수 있는 값은 없다."""
    date: str                 # YYYY-MM-DD (한국 시각)
    signups: int              # 그날 가입한 계정 수
    logins: int               # 그날 로그인한 횟수
    active_users: int         # 그날 로그인한 사용자 수 (같은 사람은 한 번만)
    returning_users: int      # 그중 이전 날에도 로그인한 적이 있는 사용자 수 (재방문)


class Overview(BaseModel):
    funnel: list[FunnelStage]
    consents: list[ConsentCount]
    deletions: DeletionStat
    status: ServiceStatus
    activity: list[DailyActivity]


# ---- 기간별 이탈 분석 (실제 기록 기준) ----
class JourneyStage(BaseModel):
    code: str
    label: str
    users: int                          # 이 단계 기록이 실제로 있는 사람
    from_previous: int | None           # 그중 바로 앞 단계 기록도 있는 사람 (첫 단계는 None)
    skipped_previous: int | None        # 바로 앞 단계 기록 없이 이 단계에 온 사람
    lost: int | None                    # 바로 앞 단계 기록은 있는데 이 단계 기록이 없는 사람
    biggest_loss: bool = False          # 마지막 단계를 뺀 가운데 lost가 가장 큰 단계


class RecordDays(BaseModel):
    bucket: str                         # 첫 4주에 본인이 직접 기록한 날짜 수: 0일·1일·2일·3일 이상
    users: int
    finished_4w: int                    # 첫 4주를 마친 사람(완료·미완료로 끝남, 체험 자동 채움 포함)
    started_next: int                   # 다음 4주를 시작한 사람


class SkippedAccount(BaseModel):
    user_id_short: str                  # 회원 번호 끝 8자리 (관리자 화면의 가입자 목록과 같은 표시)
    signed_up_kst: str


class Journey(BaseModel):
    signup_from: date | None
    signup_to: date | None
    exclude_admins: bool
    cohort: int                         # 기간에 가입한 이용 중 계정(관리자 제외 선택 시 뺀 뒤)
    admins_excluded: int
    stages: list[JourneyStage]
    record_days: list[RecordDays]
    challenge_without_prediction: list[SkippedAccount]

