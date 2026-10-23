"""캐릭터: 산 아이템(보유)과 지금 입은 조합.
user_id 칸이 있어서 탈퇴 때 함께 지워진다. 건강정보 동의 철회 때는 남긴다(HEALTH_KEEP_TABLES)."""
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class CharacterItem(Base):
    """산 아이템 한 개. 무료 아이템은 줄을 만들지 않는다."""
    __tablename__ = "character_items"
    __table_args__ = (UniqueConstraint("user_id", "item_key", name="uq_character_items_user_item"),)

    character_item_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_key: Mapped[str] = mapped_column(String(40), nullable=False)    # body:bear, color:#E8C14A
    acquired_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class UserCharacter(Base):
    """지금 입은 조합 (한 사람에 한 줄)."""
    __tablename__ = "user_characters"

    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    body: Mapped[str] = mapped_column(String(20), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False)
    eye: Mapped[str] = mapped_column(String(20), nullable=False, default="#243749", server_default="#243749")   # 눈 색
    expr: Mapped[str] = mapped_column(String(20), nullable=False)
    face: Mapped[str] = mapped_column(String(20), nullable=False)
    head: Mapped[str] = mapped_column(String(20), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)