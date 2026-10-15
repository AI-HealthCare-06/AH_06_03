"""'모든 미션을 마친 날' 계산.
홈 연속 달성·이번 주 7칸·파이 조각, 연속 배지, 5일마다 파이, 파티 연속 인증이 같이 쓴다."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import ChallengeCycle, ChallengeLog, CycleChallenge

DONE_STATUSES = {"completed", "skipped"}   # 외식 안 한 날(skipped)도 마친 걸로. 팀 확정 전 임시


async def done_days(db: AsyncSession, user_id: str) -> set[date]:
    """그 날 속한 사이클의 미션을 '모두' 마친 날짜들. 사이클이 바뀌어도 날짜로 이어서 본다."""
    rows = (await db.execute(
        select(ChallengeCycle.cycle_id, CycleChallenge.cycle_challenge_id, ChallengeLog.log_date, ChallengeLog.status)
        .join(CycleChallenge, CycleChallenge.cycle_id == ChallengeCycle.cycle_id)
        .outerjoin(ChallengeLog, ChallengeLog.cycle_challenge_id == CycleChallenge.cycle_challenge_id)
        .where(ChallengeCycle.user_id == user_id)
    )).all()
    missions: dict[str, set[str]] = {}            # 사이클 → 그 사이클의 미션들
    done: dict[tuple[str, date], set[str]] = {}   # (사이클, 날짜) → 그날 마친 미션들
    for cycle_id, cc_id, log_date, status in rows:
        missions.setdefault(cycle_id, set()).add(cc_id)
        if log_date is not None and status in DONE_STATUSES:
            done.setdefault((cycle_id, log_date), set()).add(cc_id)
    return {d for (cycle_id, d), ccs in done.items() if ccs == missions[cycle_id]}


def current_streak(days: set[date], today: date) -> int:
    """오늘(오늘 아직 안 했으면 어제)까지 이어진 날 수. 하루라도 비면 끊긴다."""
    cur = today if today in days else today - timedelta(days=1)
    n = 0
    while cur in days:
        n += 1
        cur -= timedelta(days=1)
    return n


def runs(days: set[date]) -> list[tuple[date, int]]:
    """연속 구간들: [(시작일, 길이), ...]. 연속 배지와 5일마다 파이에 쓴다."""
    result, start, prev = [], None, None
    for d in sorted(days):
        if prev is None or d != prev + timedelta(days=1):
            if start is not None:
                result.append((start, (prev - start).days + 1))
            start = d
        prev = d
    if start is not None:
        result.append((start, (prev - start).days + 1))
    return result


async def today_progress(db: AsyncSession, user_id: str, today: date) -> tuple[int, int]:
    """오늘 진행 중인 사이클의 미션 수와, 그중 오늘 마친 수 (홈의 파이 조각)."""
    cycle = (await db.execute(
        select(ChallengeCycle.cycle_id).where(
            ChallengeCycle.user_id == user_id,
            ChallengeCycle.status == "active",
            ChallengeCycle.started_on <= today,
            ChallengeCycle.ended_on >= today,
        )
    )).scalar_one_or_none()
    if cycle is None:
        return 0, 0
    mission_ids = (await db.execute(
        select(CycleChallenge.cycle_challenge_id).where(CycleChallenge.cycle_id == cycle)
    )).scalars().all()
    done = (await db.execute(
        select(ChallengeLog.cycle_challenge_id).where(
            ChallengeLog.cycle_challenge_id.in_(mission_ids),
            ChallengeLog.log_date == today,
            ChallengeLog.status.in_(DONE_STATUSES),
        )
    )).scalars().all()
    return len(set(done)), len(mission_ids)


async def home_summary(db: AsyncSession, user_id: str, today: date) -> dict:
    """홈: 연속 달성 일수, 이번 주(월~일) 7칸, 오늘 파이 조각."""
    days = await done_days(db, user_id)
    monday = today - timedelta(days=today.weekday())
    week = [{"date": monday + timedelta(days=i), "done": (monday + timedelta(days=i)) in days} for i in range(7)]
    today_done, today_total = await today_progress(db, user_id, today)
    return {
        "streak": current_streak(days, today),
        "week": week,
        "today_done": today_done,
        "today_total": today_total,
    }