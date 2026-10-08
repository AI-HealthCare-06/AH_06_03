"""동의 정책(약관 본문·버전)과 회원별 동의·철회 기록 (ERD v8 consent_policies, user_consents)."""
from datetime import datetime

from sqlalchemy import CHAR, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class ConsentPolicy(Base):
    __tablename__ = "consent_policies"
    __table_args__ = (UniqueConstraint("policy_type", "version"),)

    policy_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    policy_type: Mapped[str] = mapped_column(
        Enum("terms_of_service", "privacy", "health_data", "guardian", name="policy_type"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    purpose_text: Mapped[str] = mapped_column(Text, nullable=False)
    collection_items: Mapped[str] = mapped_column(Text, nullable=False)
    retention_policy: Mapped[str] = mapped_column(Text, nullable=False)
    withdrawal_method: Mapped[str] = mapped_column(Text, nullable=False)
    third_party_notice: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class UserConsent(Base):
    __tablename__ = "user_consents"

    user_consent_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("consent_policies.policy_id"), nullable=False)
    status: Mapped[str] = mapped_column(Enum("agreed", "withdrawn", name="consent_status"), nullable=False, default="agreed")
    consented_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
