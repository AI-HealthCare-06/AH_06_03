import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


class AttachRequest(BaseModel):
    """글에 붙일 챌린지. 내 4주 챌린지의 미션(mission_code)이나 참여 중인 공통 챌린지(common_challenge_id) 중 하나."""
    model_config = ConfigDict(extra="forbid")

    mission_code: str | None = Field(default=None, max_length=50)
    common_challenge_id: str | None = Field(default=None, max_length=36)
    party_card: bool = False          # 파티 글에서만: "파티 연속 인증 N일째" 카드를 붙인다

    @model_validator(mode="after")
    def one_of(self):
        if bool(self.mission_code) + bool(self.common_challenge_id) + bool(self.party_card) != 1:
            raise ValueError("미션, 공통 챌린지, 파티 카드 중 하나만 골라 주세요.")
        return self


class PostAttach(BaseModel):
    kind: Literal["fixed", "selected", "common", "party"]   # 고정 / 선택 / 공통 / 파티
    label: str                                     # 미션·챌린지 이름
    days: int                                      # 인증한 일수


class AttachOption(BaseModel):
    """글쓰기 화면에서 붙일 수 있는 "오늘 인증한 챌린지"."""
    mission_code: str | None
    common_challenge_id: str | None
    kind: Literal["fixed", "selected", "common"]
    label: str
    days: int


class PostCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attach: AttachRequest | None = None

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
    attach: PostAttach | None = None   # 붙인 챌린지 카드 (숨김 글에는 없다)
    photo_count: int = 0          # 붙은 사진 수 (사진 자체는 따로 받는다)
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
    author_user_id: str | None = None   # 정지·삭제 같은 계정 조치에 쓰는 작성자 번호 (관리자에게만 내려간다)
    category: str                 # 글의 카테고리 (댓글이면 달린 글의 카테고리)
    report_count: int
    pending_count: int            # 아직 처리하지 않은 신고 수
    reasons: dict[str, int]       # 사유별 건수 {"health_info": 2, "spam": 1}
    preview: str                  # 신고된 글·댓글의 본문 앞부분 (관리자만 본다)
    status: Literal["pending", "done"]
    action: str | None            # 마지막 처리 (hide / delete / dismiss)
    last_reported_at: datetime
    auto_hidden: bool = False     # 신고가 기준(서로 다른 3명)에 닿아 관리자 확인 전까지 자동으로 숨겨진 상태


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


class PhotoResult(BaseModel):
    position: int                 # 몇 번째 사진인지 (0부터)


class AdminPostItem(BaseModel):
    """관리자 글 관리 목록 한 줄 (전체 커뮤니티 글, 파티 글 제외)."""
    post_id: str
    title: str
    preview: str                  # 본문 앞부분 (관리자만 본다)
    category: str
    author_nickname: str
    author_user_id: str | None = None   # 정지·삭제 같은 계정 조치에 쓰는 작성자 번호 (관리자에게만)
    status: Literal["visible", "hidden", "deleted"]
    pending_reports: int          # 아직 처리하지 않은 신고 수
    created_at: datetime


class AdminPostList(BaseModel):
    total: int
    items: list[AdminPostItem]


class AdminPostActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["hide", "delete", "restore"]


class AdminPostActionResult(BaseModel):
    post_id: str
    status: str                   # 바뀐 뒤 상태
    handled_reports: int          # 함께 처리된 대기 신고 수
