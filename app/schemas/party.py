from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PartyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=12)
    intro: str | None = Field(default=None, max_length=60)
    challenge_code: str = Field(max_length=20, description="선택 미션 8개 중 하나 (예: NA-1)")


class PartyJoin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invite_code: str = Field(max_length=20, description="예: PAEON-7K3Q")


class PartyChallengeOption(BaseModel):
    challenge_code: str
    challenge_name: str


class PartyInfo(BaseModel):
    party_id: str
    name: str
    intro: str | None
    invite_code: str
    challenge_code: str
    challenge_name: str
    started_on: date
    member_count: int
    max_members: int

class PartyMemberView(BaseModel):
    nickname: str
    character: dict             # body, color, expr, face, head
    is_leader: bool             # 파티장 (가장 먼저 들어온 사람)
    is_me: bool
    done_today: bool            # 오늘 인증 완료
    days_total: int             # N: 들어온 날부터 오늘까지 일수
    days_done: int              # M: 그중 인증한 날 수


class PartyHome(BaseModel):
    party: PartyInfo
    day_number: int             # 파티 시작 N일째
    members: list[PartyMemberView]
    streak: int                 # 파티 연속 인증 (모두 인증한 날이 이어진 일수)
    today_all_done: bool
    today_remaining: int        # 오늘 아직 인증 안 한 파티원 수


class PartyCard(BaseModel):
    name: str
    streak: int