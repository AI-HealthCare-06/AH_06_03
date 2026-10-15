"""챌린지 기록에서 나오는 파이 적립.
- 오늘 미션 모두 완료 +5 (하루 한 번)
- '모든 미션을 마친 날'이 5·10·15…일 이어질 때마다 +10 (끊기면 1일부터)
- 4주 사이클 완주 +50
적립 장부는 pie_service가 맡고, 같은 (회원, 이유, 기준)은 한 번만 적립된다. commit은 부르는 쪽에서."""
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import pie_service, streak_service

DAILY_COMPLETE = "challenge_daily_complete"     # 오늘 미션 모두 완료
STREAK_5 = "challenge_streak_5"                 # 5일마다
CYCLE_COMPLETE = "challenge_cycle_complete"     # 4주 완주

DAILY_PIE, STREAK_PIE, CYCLE_PIE = 5, 10, 50


async def reward_after_log(db: AsyncSession, user_id: str, today: date) -> None:
    """미션 기록을 저장한 뒤 부른다. 오늘 모두 마쳤으면 +5, 연속이 5의 배수가 되면 +10."""
    done, total = await streak_service.today_progress(db, user_id, today)
    if total == 0 or done < total:
        return
    await pie_service.add(db, user_id, DAILY_PIE, DAILY_COMPLETE, today.isoformat())

    days = await streak_service.done_days(db, user_id)
    for start, length in streak_service.runs(days):
        end = date.fromordinal(start.toordinal() + length - 1)
        if start <= today <= end:
            n = (today - start).days + 1                      # 이 연속 구간에서 오늘이 몇 번째 날
            if n % 5 == 0:
                await pie_service.add(db, user_id, STREAK_PIE, STREAK_5, f"{start.isoformat()}:{n // 5}")
            break


async def reward_cycle_complete(db: AsyncSession, user_id: str, cycle_id: str) -> None:
    """사이클이 completed로 끝났을 때 부른다. +50 (사이클마다 한 번)."""
    await pie_service.add(db, user_id, CYCLE_PIE, CYCLE_COMPLETE, cycle_id)