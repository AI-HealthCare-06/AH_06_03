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