"""챌린지 파이 적립: 오늘 모두 완료 +5, 5일마다 +10(끊기면 1일부터), 4주 완주 +50."""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.challenge import ChallengeCycle, ChallengeLog, CycleChallenge
from app.models.pie import PieLedger
from app.models.user import User, UserProfile
from app.services import challenge_reward_service as reward

START = date(2026, 10, 1)
NOW = datetime(2026, 10, 1, 3, 0)

pytestmark = pytest.mark.asyncio


async def _setup(Session):
    from tests.conftest import _seed_module
    seed = _seed_module()
    async with Session() as s:
        u = User(email="r@test.kr", password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1981, 3, 1)))
        c = ChallengeCycle(user_id=u.user_id, cycle_number=1, started_on=START,
                           ended_on=START + timedelta(days=27), status="active", created_at=NOW, updated_at=NOW)
        s.add(c)
        await s.flush()
        ccs = []
        for n in (1, 2):
            cc = CycleChallenge(cycle_id=c.cycle_id, challenge_id=seed._mission_id(n), selection_type="fixed",
                                difficulty="medium", weekly_target=5, status="active")
            s.add(cc)
            ccs.append(cc)
        await s.commit()
        return u.user_id, c.cycle_id, [cc.cycle_challenge_id for cc in ccs]


async def _log(Session, cc_id, day, status="completed"):
    async with Session() as s:
        s.add(ChallengeLog(cycle_challenge_id=cc_id, log_date=day, status=status, limit_exceeded=False,
                           recorded_at=NOW, updated_at=NOW))
        await s.commit()


async def _reward(Session, uid, day):
    async with Session() as s:
        await reward.reward_after_log(s, uid, day)
        await s.commit()


async def _ledger(Session, uid):
    async with Session() as s:
        rows = (await s.execute(select(PieLedger).where(PieLedger.user_id == uid))).scalars().all()
        return sorted((r.reason, r.ref_key, r.delta) for r in rows)


async def test_하나만_마치면_적립하지_않는다(db_session):
    uid, _, ccs = await _setup(db_session)
    await _log(db_session, ccs[0], START)
    await _reward(db_session, uid, START)
    assert await _ledger(db_session, uid) == []


async def test_모두_마치면_하루_한_번_5파이(db_session):
    uid, _, ccs = await _setup(db_session)
    for cc in ccs:
        await _log(db_session, cc, START)
    await _reward(db_session, uid, START)
    await _reward(db_session, uid, START)          # 같은 날 다시 불러도 한 번만
    assert await _ledger(db_session, uid) == [(reward.DAILY_COMPLETE, "2026-10-01", 5)]


async def test_5일마다_10파이_끊기면_다시_1일부터(db_session):
    uid, _, ccs = await _setup(db_session)
    days = [START + timedelta(days=i) for i in range(5)]                    # 10/1~10/5 연속 5일
    days += [START + timedelta(days=i) for i in range(6, 11)]               # 10/6 비고, 10/7~10/11 다시 5일
    for d in days:
        for cc in ccs:
            await _log(db_session, cc, d)
        await _reward(db_session, uid, d)
    streak = [x for x in await _ledger(db_session, uid) if x[0] == reward.STREAK_5]
    assert streak == [(reward.STREAK_5, "2026-10-01:1", 10), (reward.STREAK_5, "2026-10-07:1", 10)]
    daily = [x for x in await _ledger(db_session, uid) if x[0] == reward.DAILY_COMPLETE]
    assert len(daily) == 10


async def test_외식_안_함_skipped도_마친_날로_센다(db_session):
    uid, _, ccs = await _setup(db_session)
    await _log(db_session, ccs[0], START)
    await _log(db_session, ccs[1], START, status="skipped")
    await _reward(db_session, uid, START)
    assert await _ledger(db_session, uid) == [(reward.DAILY_COMPLETE, "2026-10-01", 5)]


async def test_4주_완주_50파이_사이클마다_한_번(db_session):
    uid, cycle_id, _ = await _setup(db_session)
    async with db_session() as s:
        await reward.reward_cycle_complete(s, uid, cycle_id)
        await reward.reward_cycle_complete(s, uid, cycle_id)
        await s.commit()
    assert await _ledger(db_session, uid) == [(reward.CYCLE_COMPLETE, cycle_id, 50)]