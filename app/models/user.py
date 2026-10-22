from datetime import date,datetime

from sqlalchemy import CHAR, Date, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from app.core import pii
from uuid6 import uuid7

from app.core.db.databases import Base
from app.core.db.models import TimestampMixin

# 회원마다 붙는 고유 번호 생성
def new_id() -> str:
    """새 번호를 만든다. CHAR(36) 칸에 넣을 수 있게 글자로 바꾼다. """
    return str(uuid7())

class _EmailComparator(Comparator):
    """쿼리에서 User.email == "a@b.kr" 라고 쓰면 찾기용 지문 비교(User.email_hash == 지문)로 바꾼다.
    잠근 이메일은 부분 검색·정렬을 할 수 없으므로, 그런 연산은 조용히 틀리지 않게 바로 오류를 낸다."""

    def __eq__(self, other):
        return self.__clause_element__() == pii.email_hash(other)

    def __ne__(self, other):
        return self.__clause_element__() != pii.email_hash(other)

    def in_(self, others):
        return self.__clause_element__().in_([pii.email_hash(o) for o in others])

    def operate(self, op, *other, **kwargs):
        raise NotImplementedError("이메일은 암호화되어 있어 정확히 같은 이메일(==, !=, in_)로만 찾을 수 있습니다.")


# 회원 카트 표
class User(Base, TimestampMixin):
    __tablename__="users"
    __table_args__=(Index("uq_users_email_hash", "email_hash", unique=True),)

    user_id: Mapped[str]=mapped_column(CHAR(36), primary_key=True, default=new_id)
    # 이메일은 잠가서(email_enc) 저장하고, 로그인·중복 확인은 찾기용 지문(email_hash)으로 한다 (app/core/pii.py).
    # 코드에서는 user.email로 읽고 쓰면 두 칸이 같이 채워진다. 이메일로 찾을 때는 User.email_hash == pii.email_hash(이메일).
    email_enc: Mapped[str]=mapped_column(pii.EncryptedText, nullable=False)
    email_hash: Mapped[str]=mapped_column(CHAR(64), nullable=False)   # 고유 인덱스 uq_users_email_hash (마이그레이션 3583058d4b4f)
    password_hash: Mapped[str]=mapped_column(String(255), nullable=False)
    status: Mapped[str]=mapped_column(
        Enum("active", "deleted", "pending_guardian", name="user_status"), nullable=False, default="active"
    )
    deleted_at: Mapped[datetime | None]=mapped_column(DateTime, nullable=True)
    suspended_until: Mapped[datetime | None]=mapped_column(DateTime, nullable=True)   # 이 시각(UTC)까지 이용 정지. 영구 정지는 9999-12-31

    @hybrid_property
    def email(self) -> str:
        return self.email_enc

    @email.inplace.setter
    def _email_setter(self, value: str) -> None:
        """정리한 이메일을 잠그고 지문도 같이 바꾼다(탈퇴 익명화 때도 지문이 새 값으로 바뀌어 같은 이메일로 재가입 가능)."""
        norm = pii.normalize_email(value)
        self.email_enc = norm
        self.email_hash = pii.email_hash(norm)

    @email.inplace.comparator
    @classmethod
    def _email_comparator(cls) -> "_EmailComparator":
        return _EmailComparator(cls.email_hash)

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