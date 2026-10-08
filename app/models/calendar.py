"""캘린더 테이블 설계도: 날짜별 일기·사진, 건강 할 일. (API 명세서에 없는 화면 기능이라 새로 정의함)"""
from datetime import date, datetime

from sqlalchemy import CHAR, Boolean, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class CalendarEntry(Base):
    """📅 하루치 일기와 사진 (사용자·날짜당 1건)."""
    __tablename__ = "calendar_entries"
    __table_args__ = (UniqueConstraint("user_id", "entry_date"),)

    entry_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    diary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 화면이 줄여서 보내는 이미지(data URL). 파일로 두면 배포 때 컨테이너가 바뀌면서 사라질 수 있어 DB에 둔다.
    photo_data: Mapped[str | None] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class HealthTodo(Base):
    """✅ 날짜별 건강 할 일 (예: 스쿼트 20개 3세트)."""
    __tablename__ = "health_todos"
    __table_args__ = (Index("ix_health_todos_user_date", "user_id", "todo_date"),)

    todo_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    todo_date: Mapped[date] = mapped_column(Date, nullable=False)
    text: Mapped[str] = mapped_column(String(200), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
