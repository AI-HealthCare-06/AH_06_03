from pydantic import BaseModel, ConfigDict, Field


class CharacterView(BaseModel):
    """지금 입은 조합 (화면이 캐릭터를 그릴 때 쓰는 값)."""
    body: str
    color: str
    eye: str = "#243749"   # 눈 색 (옛 화면이 보내지 않으면 기본 검정)
    expr: str
    face: str
    head: str


class CharacterSave(CharacterView):
    model_config = ConfigDict(extra="forbid")


class ItemView(BaseModel):
    key: str
    label: str
    price: int          # 0이면 기본(무료)
    owned: bool         # 무료이거나 산 아이템이면 True


class SlotView(BaseModel):
    slot: str           # body / color / eye / expr / face / head
    items: list[ItemView]


class ItemsResult(BaseModel):
    balance: int        # 내 파이 잔액
    slots: list[SlotView]


class BuyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_key: str = Field(max_length=40, description="예: body:bear, color:#E8C14A")