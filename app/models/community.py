"""커뮤니티: 닉네임, 글, 댓글, 좋아요, 신고.

모든 표에 user_id 칸이 있어서 회원 탈퇴 때 함께 지워진다. 건강정보가 아니라서 동의 철회로는 지우지 않는다.
신고는 글이나 댓글이 지워지면 FK CASCADE로 같이 사라진다.
"""
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id

CATEGORIES = ("diet", "exercise", "challenge", "tips")           # 식단, 운동, 챌린지 인증, 고민과 꿀팁
REPORT_REASONS = ("health_info", "spam", "abuse", "other")       # 건강정보 포함, 광고·스팸, 욕설·비방, 기타


class CommunityProfile(Base):
    """커뮤니티에서 쓰는 닉네임. 닉네임을 정해야 글·댓글·공통 챌린지를 쓸 수 있다."""
    __tablename__ = "community_profiles"

    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    nickname: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CommunityPost(Base):
    __tablename__ = "community_posts"

    post_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="visible")   # visible / hidden / deleted
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)   # UTC
    # 글에 붙인 챌린지 카드 (미션 이름과 인증 일수만, 올릴 때의 값을 그대로 저장한다. 혈압·걸음 수 같은 수치는 담지 않는다)
    attach_kind: Mapped[str | None] = mapped_column(String(10), nullable=True)           # fixed / selected / common
    attach_label: Mapped[str | None] = mapped_column(String(150), nullable=True)
    attach_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 파티 글이면 그 파티 번호. 파티원에게만 보이고, 전체 커뮤니티 목록에는 나오지 않는다 (파티가 없어지면 글도 같이 지워진다)
    party_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("parties.party_id", ondelete="CASCADE"), nullable=True, index=True
    )


class CommunityComment(Base):
    __tablename__ = "community_comments"

    comment_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("community_posts.post_id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="visible")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CommunityLike(Base):
    __tablename__ = "community_likes"
    __table_args__ = (UniqueConstraint("post_id", "user_id"),)

    like_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("community_posts.post_id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )


class CommunityReport(Base):
    """신고 한 건. 한 사람이 같은 글·댓글을 두 번 신고할 수 없다. 처리하면 같은 대상의 신고에 한꺼번에 처리 결과가 붙는다."""
    __tablename__ = "community_reports"
    __table_args__ = (UniqueConstraint("user_id", "target_key"),)

    report_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    post_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("community_posts.post_id", ondelete="CASCADE"), nullable=True, index=True
    )
    comment_id: Mapped[str | None] = mapped_column(
        CHAR(36), ForeignKey("community_comments.comment_id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[str] = mapped_column(          # 신고한 사람 (탈퇴하면 이 신고도 지워진다)
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_key: Mapped[str] = mapped_column(String(50), nullable=False)  # "post:번호" 또는 "comment:번호" (NULL은 UNIQUE에서 구분되지 않아 따로 둔다)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    action: Mapped[str | None] = mapped_column(String(10), nullable=True)         # hide / delete / dismiss, 없으면 처리 대기
    handled_by: Mapped[str | None] = mapped_column(String(255), nullable=True)    # 처리한 관리자 이메일
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
