from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProofType = Literal["steps", "self"]
State = Literal["upcoming", "active", "ended"]


class Rewards(BaseModel):
    first: int
    second: int
    third: int
    complete: int


class RankRow(BaseModel):
    rank: int
    nickname: str
    days: int                     # 인증한 일수 (걸음 수 같은 값은 내보내지 않는다)
    is_me: bool


class CommonChallengeItem(BaseModel):
    challenge_id: str
    title: str
    proof_type: ProofType
    starts_on: date
    ends_on: date
    state: State
    participants: int
    max_reward: int               # 1위 보상 (목록에 "최대 300"으로 보여 줄 값)
    joined: bool
    my_rank: int | None


class CommonChallengeList(BaseModel):
    items: list[CommonChallengeItem]


class CommonChallengeDetail(CommonChallengeItem):
    target_steps: int | None
    total_days: int
    complete_min_days: int
    rewards: Rewards
    my_days: int
    certified_today: bool
    finalized: bool
    top: list[RankRow]            # 상위 5명 (내가 5위 밖이면 내 순위를 따로 덧붙인다)


class CertifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: int | None = Field(default=None, ge=0, le=200000)


class CertifyResult(BaseModel):
    my_days: int
    my_rank: int | None


class JoinResult(BaseModel):
    joined: bool = True
    participants: int


# ---------------------------------------------------------------- 관리자
class ChallengeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=2, max_length=60)
    proof_type: ProofType
    target_steps: int | None = Field(default=None, ge=1000, le=100000)
    starts_on: date
    ends_on: date
    complete_min_days: int | None = Field(default=None, ge=1)     # 비우면 전체 일수의 70%(올림)
    reward_first: int = Field(default=300, ge=0, le=100000)
    reward_second: int = Field(default=200, ge=0, le=100000)
    reward_third: int = Field(default=100, ge=0, le=100000)
    reward_complete: int = Field(default=20, ge=0, le=100000)

    @model_validator(mode="after")
    def check(self):
        if self.ends_on < self.starts_on:
            raise ValueError("끝나는 날은 시작하는 날보다 빠를 수 없어요.")
        if self.proof_type == "steps" and self.target_steps is None:
            raise ValueError("걸음 수 챌린지는 하루 목표 걸음 수가 필요해요.")
        if self.proof_type == "self" and self.target_steps is not None:
            raise ValueError("직접 인증 챌린지에는 목표 걸음 수를 넣지 않아요.")
        return self


class ChallengePatch(BaseModel):
    """시작한 뒤에는 기간·인증 방식을 바꾸지 않는다 (이미 쌓인 인증과 순위가 흔들리지 않게)."""
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=2, max_length=60)
    complete_min_days: int | None = Field(default=None, ge=1)
    reward_first: int | None = Field(default=None, ge=0, le=100000)
    reward_second: int | None = Field(default=None, ge=0, le=100000)
    reward_third: int | None = Field(default=None, ge=0, le=100000)
    reward_complete: int | None = Field(default=None, ge=0, le=100000)


class AdminChallengeItem(BaseModel):
    challenge_id: str
    title: str
    proof_type: ProofType
    target_steps: int | None
    starts_on: date
    ends_on: date
    state: State
    participants: int
    complete_min_days: int
    rewards: Rewards
    finalized_at: datetime | None


class AdminChallengeList(BaseModel):
    items: list[AdminChallengeItem]


class FinalizeResult(BaseModel):
    challenge_id: str
    ranked: int                   # 보상을 받은 순위권 인원 (최대 3)
    completed: int                # 완주 보상을 받은 인원
    total_pie: int                # 이번에 지급한 파이 합계
