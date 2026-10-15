"""파이(포인트) 장부. 다른 기능(글쓰기, 공통 챌린지, 이후 챌린지·파티)은 `add`만 부르면 된다.

- 같은 (회원, 이유, 기준 번호)는 한 번만 적립된다. 이미 있으면 아무것도 하지 않고 False를 돌려준다.
- `add`는 commit하지 않는다. 부르는 쪽이 자기 작업과 함께 commit한다.
"""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models.pie import PieLedger
from app.schemas.pie import PieEntry, PieHistory, PieSummary

# 적립 이유 이름 (장부의 reason 칸). 화면 문구는 화면에서 이 이름으로 정한다.
WELCOME = "welcome"                          # 닉네임을 처음 정할 때 시작 선물
POST_WRITE = "post_write"                    # 커뮤니티 글쓰기
RANK = "common_challenge_rank"               # 공통 챌린지 순위 보상
COMPLETE = "common_challenge_complete"       # 공통 챌린지 완주 보상


def kst_day_start_utc(now: datetime | None = None) -> datetime:
    """오늘(한국 날짜)이 시작된 시각을 UTC로 돌려준다."""
    now = now or utcnow()
    kst = now + timedelta(hours=9)
    return kst.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=9)


async def add(db: AsyncSession, user_id: str, delta: int, reason: str, ref_key: str) -> bool:
    """장부에 적립한다 (commit은 부르는 쪽에서). 같은 일로 이미 적립했다면 건너뛰고 False."""
    exists = (await db.execute(select(PieLedger.entry_id).where(
        PieLedger.user_id == user_id, PieLedger.reason == reason, PieLedger.ref_key == ref_key))).first()
    if exists is not None or delta == 0:
        return False
    try:
        async with db.begin_nested():       # 동시에 같은 적립이 들어와도 이 줄만 취소하고, 부르는 쪽의 작업은 살린다
            db.add(PieLedger(user_id=user_id, delta=delta, reason=reason, ref_key=ref_key, created_at=utcnow()))
            await db.flush()
    except IntegrityError:
        return False
    return True


async def balance(db: AsyncSession, user_id: str) -> int:
    return int((await db.execute(
        select(func.coalesce(func.sum(PieLedger.delta), 0)).where(PieLedger.user_id == user_id))).scalar_one())


async def count_today(db: AsyncSession, user_id: str, reason: str) -> int:
    """오늘(한국 날짜) 이 이유로 적립된 횟수 — "하루 최대 N번" 제한에 쓴다."""
    return int((await db.execute(select(func.count()).select_from(PieLedger).where(
        PieLedger.user_id == user_id, PieLedger.reason == reason,
        PieLedger.created_at >= kst_day_start_utc()))).scalar_one())


def _entry(r: PieLedger) -> PieEntry:
    return PieEntry(reason=r.reason, delta=r.delta, created_at=r.created_at)


async def summary(db: AsyncSession, user_id: str) -> PieSummary:
    rows = (await db.execute(select(PieLedger).where(PieLedger.user_id == user_id)
                             .order_by(PieLedger.created_at.desc(), PieLedger.entry_id).limit(5))).scalars().all()
    return PieSummary(balance=await balance(db, user_id), recent=[_entry(r) for r in rows])


async def history(db: AsyncSession, user_id: str, limit: int, offset: int) -> PieHistory:
    total = int((await db.execute(select(func.count()).select_from(PieLedger)
                                  .where(PieLedger.user_id == user_id))).scalar_one())
    rows = (await db.execute(select(PieLedger).where(PieLedger.user_id == user_id)
                             .order_by(PieLedger.created_at.desc(), PieLedger.entry_id)
                             .limit(limit).offset(offset))).scalars().all()
    return PieHistory(balance=await balance(db, user_id), total=total, items=[_entry(r) for r in rows])
