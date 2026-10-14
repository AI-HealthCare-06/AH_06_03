import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal["diet", "exercise", "challenge", "tips"]
Reason = Literal["health_info", "spam", "abuse", "other"]


def _strip(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("내용을 입력해 주세요.")
    return v


class NicknameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str = Field(min_length=2, max_length=10)

    @field_validator("nickname")
    @classmethod
    def clean(cls, v: str) -> str:
        v = v.strip()
        # 한글·영문·숫자·밑줄만 (이메일·전화번호·링크가 닉네임으로 노출되지 않게)
        if not re.fullmatch(r"[0-9A-Za-z가-힣_]{2,10}", v):
            raise ValueError("닉네임은 한글·영문·숫자·밑줄로 2~10자로 적어 주세요.")
        return v


class MyCommunity(BaseModel):
    nickname: str | None          # 아직 정하지 않았으면 None
    pie_gift: int = 0             # 방금 닉네임을 처음 정해서 받은 시작 선물 (그 밖에는 0)


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Category
    title: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=1000)

    @field_validator("title", "body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        return _strip(v)


class PostItem(BaseModel):
    post_id: str
    category: str
    title: str
    preview: str                  # 본문 앞부분 (목록용). 숨김 처리된 내 글은 빈 값
    author_nickname: str
    created_at: datetime
    like_count: int
    comment_count: int
    liked_by_me: bool
    mine: bool
    hidden: bool                  # 운영 정책으로 숨김 처리된 내 글 (다른 사람에게는 목록에 나오지 않는다)
    notice: str | None = None     # hidden일 때 보여 줄 안내


class PostList(BaseModel):
    total: int
    items: list[PostItem]


class PostDetail(PostItem):
    body: str


class PostCreated(PostDetail):
    pie_gain: int = 0             # 이 글로 받은 파이 (하루 3번까지만 받고 이후는 0)


class LikeResult(BaseModel):
    liked: bool
    like_count: int


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=300)

    @field_validator("body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        return _strip(v)


class CommentItem(BaseModel):
    comment_id: str
    body: str
    author_nickname: str
    created_at: datetime
    mine: bool


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class ReportResult(BaseModel):
    reported: bool = True


# ---------------------------------------------------------------- 관리자 (신고)
class AdminReportItem(BaseModel):
    target_type: Literal["post", "comment"]
    target_id: str
    title: str                    # 글 제목 (댓글이면 그 댓글이 달린 글의 제목)
    author_nickname: str
    category: str                 # 글의 카테고리 (댓글이면 달린 글의 카테고리)
    report_count: int
    pending_count: int            # 아직 처리하지 않은 신고 수
    reasons: dict[str, int]       # 사유별 건수 {"health_info": 2, "spam": 1}
    preview: str                  # 신고된 글·댓글의 본문 앞부분 (관리자만 본다)
    status: Literal["pending", "done"]
    action: str | None            # 마지막 처리 (hide / delete / dismiss)
    last_reported_at: datetime


class AdminReportList(BaseModel):
    total: int
    pending_total: int            # 처리 대기 대상 수 (메뉴의 숫자)
    items: list[AdminReportItem]


class ReportActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["hide", "delete", "dismiss"]


class ReportActionResult(BaseModel):
    target_type: str
    target_id: str
    action: str
    handled: int                  # 처리된 신고 수
