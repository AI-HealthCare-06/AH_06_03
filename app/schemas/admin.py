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
