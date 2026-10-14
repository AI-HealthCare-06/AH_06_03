from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InquiryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("title", "body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("내용을 입력해 주세요.")
        return v


class InquiryItem(BaseModel):
    inquiry_id: str
    title: str
    created_at: datetime
    answered: bool
    unread: bool          # 답변이 왔는데 아직 열어 보지 않음


class InquiryList(BaseModel):
    unread: int           # 안 읽은 답변 수 (메뉴의 빨간 점)
    items: list[InquiryItem]


class InquiryDetail(BaseModel):
    inquiry_id: str
    title: str
    body: str
    created_at: datetime
    answer: str | None
    answered_at: datetime | None


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=2000)

    @field_validator("answer")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("답변을 입력해 주세요.")
        return v


class AdminInquiryItem(BaseModel):
    inquiry_id: str
    user_id_short: str    # 계정 번호 끝 8자 (이메일은 보지 않는다)
    title: str
    created_at: datetime
    answered: bool


class AdminInquiryList(BaseModel):
    total: int
    items: list[AdminInquiryItem]


class AdminInquiryDetail(BaseModel):
    inquiry_id: str
    user_id_short: str
    title: str
    body: str
    created_at: datetime
    answer: str | None
    answered_by: str | None
    answered_at: datetime | None


# ---------------------------------------------------------------- 비회원 문의
class GuestInquiryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=1000)
    website: str | None = Field(default=None, max_length=200)   # 사람 눈에 안 보이는 숨은 칸 (봇이 채우면 저장하지 않는다)

    @field_validator("title", "body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("내용을 입력해 주세요.")
        return v


class GuestInquiryCreated(BaseModel):
    code: str             # 조회 번호 (이때 한 번만 알려 준다)


class GuestInquiryView(BaseModel):
    title: str
    body: str
    created_at: datetime
    answer: str | None
    answered_at: datetime | None


class AdminGuestItem(BaseModel):
    inquiry_id: str
    title: str
    created_at: datetime
    answered: bool


class AdminGuestList(BaseModel):
    total: int
    items: list[AdminGuestItem]


class AdminGuestDetail(BaseModel):
    inquiry_id: str
    title: str
    body: str
    created_at: datetime
    answer: str | None
    answered_by: str | None
    answered_at: datetime | None
