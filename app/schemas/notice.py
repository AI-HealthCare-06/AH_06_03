"""서비스 안 공지 입출력 양식. 시각은 모두 UTC이고, 화면이 한국 시각으로 바꿔 보여 준다.
내용은 글자 그대로(일반 글)이므로 화면에서는 HTML로 해석하지 말고 글자로만 보여 줘야 한다."""
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _to_utc_naive(value: datetime | None) -> datetime | None:
    """시간대가 붙어 오면 UTC로 바꾸고, 안 붙어 오면 UTC로 본다. 저장은 시간대 표시 없는 UTC로 한다."""
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


class NoticeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=2000)
    starts_at: datetime | None = Field(default=None, description="보이기 시작할 시각(UTC). 비우면 지금")
    ends_at: datetime | None = Field(default=None, description="보이기를 끝낼 시각(UTC). 비우면 계속")

    _utc = field_validator("starts_at", "ends_at")(_to_utc_naive)

    @model_validator(mode="after")
    def check_range(self) -> "NoticeCreate":
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("끝나는 시각은 시작하는 시각보다 뒤여야 합니다.")
        return self


class NoticePatch(BaseModel):
    """고칠 것만 보낸다. end_now=true면 지금 바로 내린다."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=100)
    body: str | None = Field(default=None, min_length=1, max_length=2000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    end_now: bool | None = None

    _utc = field_validator("starts_at", "ends_at")(_to_utc_naive)

    @model_validator(mode="after")
    def check_not_empty(self) -> "NoticePatch":
        if all(v is None for v in (self.title, self.body, self.starts_at, self.ends_at, self.end_now)):
            raise ValueError("고칠 값을 하나 이상 보내 주세요.")
        if self.end_now and self.ends_at is not None:
            raise ValueError("end_now와 ends_at은 같이 보낼 수 없습니다.")
        return self


class NoticePublic(BaseModel):
    """누구에게나 보이는 공지. 쓴 사람은 담지 않는다."""
    notice_id: str
    title: str
    body: str
    starts_at: datetime
    ends_at: datetime | None


class NoticeAdmin(NoticePublic):
    status: str                      # upcoming(예정) | active(게시 중) | ended(종료)
    created_by: str
    created_at: datetime
    updated_at: datetime | None
