"""챌린지 리마인드 푸시: 아침 8시(아침 식사 미션), 저녁 8시(오늘 미션 남음)."""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.challenge import Challenge, ChallengeCycle, ChallengeLog, CycleChallenge
from app.models.push import PushSetting, PushSubscription
from app.models.user import User, UserProfile
from app.services import push_service, reminder_service as rs
from tests.conftest import make_program

pytestmark = pytest.mark.asyncio

TODAY = date(2026, 10, 21)          # 수요일
NOW = datetime(2026, 10, 21, 0, 0)


@pytest.fixture(autouse=True)
def fake_push(monkeypatch):
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", "test-key")
    sent = []
    monkeypatch.setattr(push_service, "_webpush", lambda sub, payload: sent.append((sub.user_id, payload)))
    return sent


async def _code_id(s, code):
    return (await s.execute(select(Challenge.challenge_id).where(Challenge.challenge_code == code))).scalar_one()


async def _user(Session, email, codes=("BRK-1", "ACT-1"), logged=(), breakfast_on=True):
    """진행 중 사이클(codes 미션) + 구독 하나를 가진 사람. logged에 있는 미션은 오늘 기록함."""
    async with Session() as s:
        u = User(email=email, password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1990, 1, 1)))
        s.add(PushSubscription(user_id=u.user_id, endpoint=f"https://push.example.com/{email}", p256dh="p", auth="a", created_at=NOW))
        if not breakfast_on:
            s.add(PushSetting(user_id=u.user_id, comment=True, inquiry=True, party=True, challenge=True,
                              breakfast=False, updated_at=NOW))
        program = make_program(u.user_id, now=NOW)
        s.add(program)
        await s.flush()
        c = ChallengeCycle(user_id=u.user_id, program_id=program.program_id,cycle_number=1, started_on=TODAY - timedelta(days=3),
                           ended_on=TODAY + timedelta(days=24), status="active", created_at=NOW, updated_at=NOW)
        s.add(c)
        await s.flush()
        for code in codes:
            cc = CycleChallenge(cycle_id=c.cycle_id, challenge_id=await _code_id(s, code), selection_type="fixed",
                                difficulty="medium", weekly_target=5, status="active")
            s.add(cc)
            await s.flush()
            if code in logged:
                s.add(ChallengeLog(cycle_challenge_id=cc.cycle_challenge_id, log_date=TODAY, status="completed",
                                   limit_exceeded=False, recorded_at=NOW, updated_at=NOW))
        await s.commit()
        return u.user_id


async def test_문구는_조건에_맞는_것_중_직전_문구를_뺀다():
    for _ in range(30):
        m = rs.pick(rs.EVENING, {"always", "none"}, last_id=1)
        assert m[3] in {"always", "none"} and m[0] != 1
    assert rs.pick(rs.BREAKFAST, {"always"}, last_id=1)[0] in {2, 3, 4, 5, 6}     # 평일엔 주말 문구(7) 없음


async def test_아침_식사_알림은_미션이_있고_아직_기록_안_한_사람에게만(db_session, fake_push):
    a = await _user(db_session, "a@t.kr")                                   # 받음
    await _user(db_session, "b@t.kr", logged=("BRK-1",))                   # 이미 기록함
    await _user(db_session, "c@t.kr", breakfast_on=False)                   # 알림 꺼 둠
    await _user(db_session, "d@t.kr", codes=("ACT-1",))                     # 아침 식사 미션 없음
    async with db_session() as s:
        st = await rs.send_breakfast(s, TODAY)
    assert (st.targets, st.sent, st.skipped) == (1, 1, 0)
    assert [u for u, _ in fake_push] == [a]
    async with db_session() as s:
        assert (await s.get(PushSetting, a)).last_breakfast_id in {1, 2, 3, 4, 5, 6}   # 직전 문구 저장


async def test_저녁_리마인드는_오늘_미션이_남은_사람에게만(db_session, fake_push):
    a = await _user(db_session, "a@t.kr", logged=("BRK-1",))                # 하나 남음 → 받음
    await _user(db_session, "b@t.kr", logged=("BRK-1", "ACT-1"))            # 다 함 → 안 받음
    async with db_session() as s:
        assert (await rs.send_evening(s, TODAY)).sent == 1
    assert [u for u, _ in fake_push] == [a]
    async with db_session() as s:
        assert (await s.get(PushSetting, a)).last_challenge_id in {1, 2, 3, 4}     # 일부 기록 → partial·always 후보


async def test_같은_날_다시_돌리면_이미_받은_사람만_빠진다(db_session, fake_push, monkeypatch):
    a = await _user(db_session, "a@t.kr")
    b = await _user(db_session, "b@t.kr")

    def b_fails_once(sub, payload):                                         # 처음엔 b가 실패 (중간에 멈춘 것처럼)
        if sub.user_id == b and not getattr(b_fails_once, "done", False):
            b_fails_once.done = True
            raise RuntimeError("network")
        fake_push.append((sub.user_id, payload))

    monkeypatch.setattr(push_service, "_webpush", b_fails_once)
    async with db_session() as s:
        st = await rs.send_breakfast(s, TODAY)
    assert (st.sent, st.failed) == (1, 1) and [u for u, _ in fake_push] == [a]
    async with db_session() as s:                                           # 다시 돌림
        st = await rs.send_breakfast(s, TODAY)
    assert (st.targets, st.sent, st.skipped) == (2, 1, 1)                   # a는 건너뛰고 b만 받음
    assert [u for u, _ in fake_push] == [a, b]
    async with db_session() as s:                                           # 다음 날은 다시 받음
        assert (await rs.send_breakfast(s, TODAY + timedelta(days=1))).sent == 2


@pytest.mark.parametrize("hour,expected_quiet", [(6, True), (7, False), (21, False), (22, True)])
async def test_밤_10시부터_아침_7시_전까지는_보내지_않는다(monkeypatch, hour, expected_quiet):
    from app.scripts import send_reminders as sr
    monkeypatch.setattr(sr, "utcnow", lambda: datetime(2026, 10, 21, hour) - timedelta(hours=9))
    called = []

    async def fake_send(db, today):
        called.append(today)
        return rs.Stats()

    monkeypatch.setattr(rs, "send_breakfast", fake_send)

    async def fake_db():
        yield None

    monkeypatch.setattr(sr, "async_get_db", fake_db)
    assert await sr.main("breakfast") == 0
    assert (called == []) == expected_quiet