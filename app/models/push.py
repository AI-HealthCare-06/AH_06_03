"""웹 푸시: 기기마다 구독 한 줄, 사람마다 알림 설정 한 줄.
user_id 칸이 있어서 탈퇴·건강정보 동의 철회 때 함께 지워진다(다시 동의하면 화면에서 다시 허용)."""
from datetime import date, datetime

from sqlalchemy import CHAR, Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class PushSubscription(Base):
    """기기 하나의 구독. 같은 기기(endpoint)가 다시 등록하면 새 줄 대신 갱신한다."""
    __tablename__ = "push_subscriptions"

    push_subscription_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PushSetting(Base):
    """종류별 알림 켜기·끄기 + 리마인드 직전 문구 번호·보낸 날. 줄이 없으면 모두 켜짐으로 본다."""
    __tablename__ = "push_settings"

    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    comment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)     # 댓글·답글
    inquiry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)     # 문의 답변
    party: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)       # 파티 참여
    challenge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)   # 챌린지 리마인드 (저녁 8시)
    breakfast: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)   # 아침 식사 리마인드 (아침 8시)
    last_challenge_id: Mapped[int | None] = mapped_column(Integer, nullable=True)    # 저녁 리마인드 직전 문구 번호
    last_breakfast_id: Mapped[int | None] = mapped_column(Integer, nullable=True)    # 아침 리마인드 직전 문구 번호
    challenge_sent_on: Mapped[date | None] = mapped_column(Date, nullable=True)      # 저녁 리마인드를 마지막으로 보낸 날 (하루 한 번)
    breakfast_sent_on: Mapped[date | None] = mapped_column(Date, nullable=True)      # 아침 리마인드를 마지막으로 보낸 날 (하루 한 번)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)