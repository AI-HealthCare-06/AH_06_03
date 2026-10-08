"""캘린더 신청서·결과지 양식."""
import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 화면이 줄여서 보내는 이미지(data URL)만 받는다. 크기는 글자 수로 제한 (약 300KB)
PHOTO_PATTERN = re.compile(r"^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$")
PHOTO_MAX_CHARS = 400_000
DIARY_MAX_CHARS = 2000


class TodoResult(BaseModel):
    todo_id: str
    todo_date: date
    text: str
    done: bool


class CalendarDayResult(BaseModel):
    """하루치: 일기·사진·건강 할 일. 내용이 있는 날만 나온다."""
    entry_date: date
    diary: str | None
    photo: str | None
    todos: list[TodoResult]


class CalendarMonthDay(BaseModel):
    """달 목록용 하루치. 사진은 용량이 커서 싣지 않고 has_photo만 알려 준다 (사진은 GET /calendar/entries/{날짜})."""
    entry_date: date
    diary: str | None
    has_photo: bool
    todos: list[TodoResult]


class EntryUpsertRequest(BaseModel):
    """일기·사진 저장. 보낸 필드만 바뀌고, 보내지 않은 필드는 그대로 둔다. photo에 null을 보내면 사진을 지운다."""
    model_config = ConfigDict(extra="forbid")

    diary: str | None = Field(default=None, max_length=DIARY_MAX_CHARS)
    photo: str | None = None

    @field_validator("photo")
    @classmethod
    def check_photo(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) > PHOTO_MAX_CHARS or not PHOTO_PATTERN.match(v):
            raise ValueError("사진은 jpeg·png·webp를 줄여서 보내 주세요 (약 300KB 이하).")
        return v


class TodoCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=200)


class TodoUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None
