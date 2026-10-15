"""파이 장부: 같은 일로 두 번 적립되지 않고, 잔액은 장부의 합계이며, 하루 횟수는 한국 날짜 기준으로 센다."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.pie import PieLedger
from app.models.user import User
from app.services import pie_service

pytestmark = pytest.mark.asyncio


async def new_user(Session, email="a@test.kr") -> str:
    async with Session() as s:
        u = User(email=email, password_hash="x", status="active")
        s.add(u)
        await s.commit()
        return u.user_id


async def test_같은_일로는_한_번만_적립된다(db_session):
    uid = await new_user(db_session)
    async with db_session() as s:
        assert await pie_service.add(s, uid, 5, "daily_complete", "2026-10-14") is True
        assert await pie_service.add(s, uid, 5, "daily_complete", "2026-10-14") is False      # 같은 (이유, 기준)
        assert await pie_service.add(s, uid, 5, "daily_complete", "2026-10-15") is True       # 기준이 다르면 새 적립
        assert await pie_service.add(s, uid, 0, "x", "none") is False                          # 0은 기록하지 않는다
        await s.commit()
    async with db_session() as s:
        assert await pie_service.balance(s, uid) == 10
        assert len((await s.execute(select(PieLedger))).scalars().all()) == 2


async def test_잔액은_회원별로_따로_센다(db_session):
    a, b = await new_user(db_session, "a@test.kr"), await new_user(db_session, "b@test.kr")
    async with db_session() as s:
        await pie_service.add(s, a, 100, "r", "1")
        await pie_service.add(s, b, 7, "r", "1")
        await pie_service.add(s, a, -30, "use", "1")           # 사용은 -로 기록한다
        await s.commit()
        assert (await pie_service.balance(s, a), await pie_service.balance(s, b)) == (70, 7)


async def test_내역은_최신순이고_요약은_최근_5건(db_session):
    uid = await new_user(db_session)
    async with db_session() as s:
        for n in range(7):
            await pie_service.add(s, uid, n + 1, "r", str(n))
        await s.commit()
    async with db_session() as s:
        summary = await pie_service.summary(s, uid)
        assert summary.balance == 28 and len(summary.recent) == 5
        page = await pie_service.history(s, uid, 3, 5)
        assert page.total == 7 and len(page.items) == 2


async def test_하루_횟수는_한국_날짜가_바뀌는_시각에_맞춰_센다(db_session):
    uid = await new_user(db_session)
    # UTC 14일 16시 = 한국 15일 새벽 1시. 그날의 시작(한국 0시)은 UTC 14일 15시다.
    now = datetime(2026, 10, 14, 16, 0)
    assert pie_service.kst_day_start_utc(now) == datetime(2026, 10, 14, 15, 0)
    now = datetime(2026, 10, 14, 14, 59)                 # 한국 23:59 → 그날 시작은 UTC 13일 15시
    assert pie_service.kst_day_start_utc(now) == datetime(2026, 10, 13, 15, 0)
    now = datetime(2026, 10, 14, 15, 0)                  # 한국 자정 → 새 날의 시작
    assert pie_service.kst_day_start_utc(now) == datetime(2026, 10, 14, 15, 0)
    async with db_session() as s:
        await pie_service.add(s, uid, 2, pie_service.POST_WRITE, "p1")
        await s.commit()
    async with db_session() as s:
        assert await pie_service.count_today(s, uid, pie_service.POST_WRITE) == 1
        row = (await s.execute(select(PieLedger))).scalar_one()
        row.created_at = row.created_at - timedelta(days=2)          # 이틀 전 적립은 오늘 횟수에 들어가지 않는다
        await s.commit()
        assert await pie_service.count_today(s, uid, pie_service.POST_WRITE) == 0


async def test_동시에_같은_적립이_들어와도_부르는_쪽의_작업은_살아남는다(db_session, monkeypatch):
    uid = await new_user(db_session)
    async with db_session() as s:
        s.add(PieLedger(user_id=uid, delta=5, reason="r", ref_key="k", created_at=datetime(2026, 10, 14)))
        await s.commit()
    async with db_session() as s:
        async def blind(*a, **k):            # "이미 있나?" 확인이 놓친 상황 (다른 요청이 그 사이에 넣음)
            class R:
                def first(self): return None
            return R()
        real = s.execute
        calls = {"n": 0}
        async def fake(stmt, *a, **k):
            calls["n"] += 1
            return await blind() if calls["n"] == 1 else await real(stmt, *a, **k)
        monkeypatch.setattr(s, "execute", fake)
        s.add(User(email="keep@test.kr", password_hash="x", status="active"))     # 부르는 쪽이 이미 해 둔 작업
        assert await pie_service.add(s, uid, 5, "r", "k") is False
        await s.commit()
    async with db_session() as s:
        assert (await s.execute(select(User).where(User.email == "keep@test.kr"))).scalar_one_or_none() is not None
        assert len((await s.execute(select(PieLedger))).scalars().all()) == 1
