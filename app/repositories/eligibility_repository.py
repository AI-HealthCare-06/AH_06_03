"""대상 확인 창고 담당. DB에 넣고 꺼내는 일만 한다."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eligibility import EligibilityAssessment


async def get_latest(db: AsyncSession, user_id: str) -> EligibilityAssessment | None:
    """이 회원의 가장 최근 대상 확인 (없으면 None: 대상 확인을 안 했거나 서버 저장 이전에 가입한 회원)."""
    result = await db.execute(
        select(EligibilityAssessment).where(EligibilityAssessment.user_id == user_id)
        .order_by(EligibilityAssessment.assessed_at.desc(), EligibilityAssessment.assessment_id.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def add(
    db: AsyncSession, user_id: str, result_code: str, age_eligible: bool, diagnosed_cad: bool,
    emergency_flag: bool, emergency_acknowledged_at: datetime | None, now: datetime,
) -> EligibilityAssessment:
    """대상 확인 한 건을 쌓는다 (이력). 저장 확정(commit)은 부른 쪽이 한다."""
    row = EligibilityAssessment(
        user_id=user_id, result_code=result_code, age_eligible=age_eligible, diagnosed_cad=diagnosed_cad,
        emergency_flag=emergency_flag, emergency_acknowledged_at=emergency_acknowledged_at, assessed_at=now,
    )
    db.add(row)
    await db.flush()
    return row
