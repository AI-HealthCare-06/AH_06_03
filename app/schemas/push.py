from pydantic import BaseModel, ConfigDict, Field


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(max_length=255)
    auth: str = Field(max_length=255)


class SubscriptionIn(BaseModel):
    """브라우저 PushSubscription.toJSON() 모양 그대로 (expirationTime 같은 다른 칸은 무시)."""
    model_config = ConfigDict(extra="ignore")
    endpoint: str = Field(max_length=500, pattern=r"^https://")
    keys: SubscriptionKeys


class SubscriptionOut(BaseModel):
    endpoint: str


class EndpointIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(max_length=500)


class PushSettings(BaseModel):
    comment: bool = True      # 댓글·답글
    inquiry: bool = True      # 문의 답변
    party: bool = True        # 파티 참여
    challenge: bool = True    # 챌린지 리마인드 (저녁 8시)
    breakfast: bool = True    # 아침 식사 리마인드 (아침 8시)


class PushSettingsIn(BaseModel):
    """바꿀 것만 보낸다 (안 보낸 칸은 그대로)."""
    model_config = ConfigDict(extra="forbid")
    comment: bool | None = None
    inquiry: bool | None = None
    party: bool | None = None
    challenge: bool | None = None
    breakfast: bool | None = None


class VapidKey(BaseModel):
    public_key: str           # 화면이 구독할 때 applicationServerKey로 쓴다 (비어 있으면 서버에 키가 없음)