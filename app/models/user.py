from datetime import date,datetime

from sqlalchemy import CHAR, Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from app.core.db.databases import Base
from app.core.db.models import TimestampMixin

# 회원마다 붙는 고유 번호 생성
def new_id() -> str:
    """새 번호를 만든다. CHAR(36) 칸에 넣을 수 있게 글자로 바꾼다. """
    return str(uuid7())

# 회원 카트 표
class User(Base, TimestampMixin):
    __tablename__="users"

    user_id: Mapped[str]=mapped_column(CHAR(36), primary_key=True, default=new_id)
    email: Mapped[str]=mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str]=mapped_column(String(255), nullable=False)
    status: Mapped[str]=mapped_column(
        Enum("active", "deleted", "pending_guardian", name="user_status"), nullable=False, default="active"
    )
    deleted_at: Mapped[datetime | None]=mapped_column(DateTime, nullable=True)

# 보호자 정보 추가 표
class GuardianConsentVerification(Base):
    """만 14세 미만 회원의 법정대리인 동의 기록 (REQ-CONSENT-003)."""
    __tablename__ = "guardian_consent_verifications"

    guardian_verification_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    guardian_name_enc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    guardian_relation: Mapped[str] = mapped_column(
        Enum("parent", "legal_guardian", name="guardian_relation"), nullable=False
    )
    guardian_contact_enc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verification_method: Mapped[str] = mapped_column(Enum("sms", "email", name="verification_method"), nullable=False)
    verification_status: Mapped[str] = mapped_column(
        Enum("pending", "verified", "expired", "purged", name="guardian_verification_status"),
        nullable=False,
        default="pending",
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    purge_due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
                                                       

# 회원 추가 정보 표
class UserProfile(Base, TimestampMixin):
    __tablename__="user_profiles"

    user_id: Mapped[str]=mapped_column(CHAR(36), ForeignKey("users.user_id"), primary_key=True)
    sex: Mapped[str | None]=mapped_column(Enum("male","female", name="sex_type"),nullable=True)
    birth_date: Mapped[date]=mapped_column(Date, nullable=False)


# 회원 세션 표
class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)