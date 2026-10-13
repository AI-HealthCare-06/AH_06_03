"""관리자 최소 기능 입출력 양식: 챌린지 카테고리·미션의 노출과 카테고리 순서."""
from pydantic import BaseModel, ConfigDict, Field, model_validator


class AdminMission(BaseModel):
    challenge_id: str
    challenge_code: str
    challenge_name: str
    mission_role: str
    active: bool
    switchable: bool  # 노출 스위치가 듣는 건 선택 미션뿐 (고정·대체 미션은 규칙이 정한다)


class AdminCategory(BaseModel):
    category_id: str
    category_code: str
    category_name: str
    display_order: int
    active: bool
    switchable: bool  # 선택 미션이 하나라도 있는 카테고리만 스위치가 의미가 있다
    missions: list[AdminMission]


class CategoryPatch(BaseModel):
    """카테고리 고치기: 보낸 것만 바뀐다."""
    model_config = ConfigDict(extra="forbid")

    active: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=99)

    @model_validator(mode="after")
    def check_not_empty(self) -> "CategoryPatch":
        if self.active is None and self.display_order is None:
            raise ValueError("고칠 값(active 또는 display_order)을 보내 주세요.")
        return self


class MissionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool


# ---- 가입자·통계·삭제·열람 기록 (건강 수치는 어디에도 담지 않는다) ----
class AdminUserRow(BaseModel):
    user_id_short: str
    user_id: str
    email_masked: str
    status: str                 # active / deleted
    joined_at: str
    stage: str                  # signup / eligibility / health / survey / prediction / challenge
    health_consent: str         # agreed / withdrawn / none


class AdminUserList(BaseModel):
    total: int
    items: list[AdminUserRow]


class AdminConsentItem(BaseModel):
    policy_type: str
    version: str
    status: str
    consented_at: str
    withdrawn_at: str | None


class AdminUserDetail(AdminUserRow):
    stages_done: list[str]
    consents: list[AdminConsentItem]
    cycles: int                 # 시작한 챌린지 사이클 수


class PurgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patterns: list[str] = Field(min_length=1, max_length=5)   # 이메일 LIKE 패턴, 예: %@a.com
    apply: bool = False
    confirm_count: int | None = None   # 실제로 지울 때 미리보기에서 본 인원수를 그대로 보낸다


class PurgeTarget(BaseModel):
    email_masked: str
    status: str


class PurgeResult(BaseModel):
    count: int
    targets: list[PurgeTarget]
    applied: bool
    done: int = 0
    failed: int = 0

class MissionStat(BaseModel):
    """미션 하나의 통계. 개인 식별 정보 없이 숫자만."""
    challenge_code: str
    challenge_name: str
    category_name: str
    mission_role: str
    assigned_count: int      # 사이클에 들어간 횟수 (고정·대체 포함)
    selected_count: int      # 사용자가 직접 고른 횟수
    active_count: int        # 진행 중
    completed_count: int     # 4주 달성
    incomplete_count: int    # 4주를 마쳤지만 목표 미달
    stopped_count: int       # 중간에 그만둠(포기)
    completion_rate: float | None   # 달성 / (달성 + 미달). 끝난 것이 없으면 None
    giving_up_rate: float | None    # 포기 / (달성 + 미달 + 포기). 끝난 것이 없으면 None
    avg_logged_days: float | None   # 미션 한 번당 기록한 날 평균
    avg_completed_days: float | None  # 미션 한 번당 목표를 지킨 날 평균


class CycleStat(BaseModel):
    """4주 사이클 전체 통계."""
    total: int
    active: int
    completed: int
    incomplete: int
    stopped: int
    completion_rate: float | None   # 4주 완료율: 완료 / (완료 + 미달)
    giving_up_rate: float | None    # 포기율: 중단 / (완료 + 미달 + 중단)
    users_started: int              # 챌린지를 시작한 사용자 수


class ChallengeStats(BaseModel):
    missions: list[MissionStat]
    cycles: CycleStat
