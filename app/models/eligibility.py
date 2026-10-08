"""이용 적합성·응급 확인 기록 (ERD v8 eligibility_assessments). 확인할 때마다 한 줄씩 쌓는다.
응급 증상 원문은 저장하지 않는다 (NFR-SEC-003): 응급 여부와 안내를 확인하고 진행한 시각만 남긴다."""
from datetime import datetime

from sqlalchemy import CHAR, Boolean, DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.databases import Base
from app.models.user import new_id


class EligibilityAssessment(Base):
    __tablename__ = "eligibility_assessments"
    __table_args__ = (Index("ix_eligibility_assessments_user_assessed", "user_id", "assessed_at"),)

    assessment_id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    result_code: Mapped[str] = mapped_column(
        Enum("eligible", "age_out", "diagnosed", "emergency", name="eligibility_result"), nullable=False
    )
    age_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    diagnosed_cad: Mapped[bool] = mapped_column(Boolean, nullable=False)   # 협심증·심근경색 등 관상동맥질환 진단 여부 (W03)
    emergency_flag: Mapped[bool] = mapped_column(Boolean, nullable=False)
    emergency_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
