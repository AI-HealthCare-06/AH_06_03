"""대상 확인 창고 담당. DB에 넣고 꺼내는 일만 한다."""
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.eligibility import UserEligibility


async def get_by_user(db: AsyncSession, user_id: str) -> UserEligibility | None:
    """이 회원의 대상 확인 답 (없으면 None: 대상 확인을 아직 안 했거나 서버 저장 이전에 가입한 회원)."""
    return await db.get(UserEligibility, user_id)


async def upsert(db: AsyncSession, user_id: str, age_band: str, chd: bool, emergency: str, now: datetime) -> UserEligibility:
    """대상 확인 답을 저장한다 (있으면 덮어쓴다). 저장 확정(commit)은 부른 쪽이 한다."""
    row = await db.get(UserEligibility, user_id)
    if row is None:
        row = UserEligibility(user_id=user_id, age_band=age_band, chd=chd, emergency=emergency, updated_at=now)
        db.add(row)
    else:
        row.age_band, row.chd, row.emergency, row.updated_at = age_band, chd, emergency, now
    return row
