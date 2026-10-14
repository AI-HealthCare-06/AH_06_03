"""관리자 운영 현황 입출력 양식: 진행 단계별 인원, 동의·삭제 현황, 서비스 상태. 숫자만 담고 사용자를 알아볼 값은 없다."""
from datetime import datetime

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
