"""파티: 후보 8개, 최대 6명, 1인 1파티, 하루 한 번 인증, 전원 인증 +3, N일 중 M일, 파티 연속 인증, 나가기."""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.models.party import Party, PartyCheckin, PartyMember
from app.models.pie import PieLedger
from app.models.user import User, UserProfile
from app.services import party_service as ps
from app.services.challenge_service import today_kst

pytestmark = pytest.mark.asyncio


async def _user(Session, email):
    async with Session() as s:
        u = User(email=email, password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1990, 1, 1)))
        await s.commit()
        return u.user_id


async def _party(Session, owner):
    async with Session() as s:
        code = (await ps.challenge_options(s))[0].challenge_code
        return await ps.create(s, owner, "아침걷기", "같이 걸어요", code)


async def test_후보는_선택_미션_8개_흡연_음주_제외(db_session):
    async with db_session() as s:
        codes = [o.challenge_code for o in await ps.challenge_options(s)]
    assert len(codes) == 8 and "SMK-1" not in codes and "ALC-1" not in codes


async def test_흡연_미션으로는_만들_수_없다(db_session):
    a = await _user(db_session, "a@t.kr")
    async with db_session() as s:
        with pytest.raises(AppError):
            await ps.create(s, a, "금연단", None, "SMK-1")


async def test_최대_6명_7번째는_거절(db_session):
    ids = [await _user(db_session, f"u{i}@t.kr") for i in range(7)]
    info = await _party(db_session, ids[0])
    for uid in ids[1:6]:
        async with db_session() as s:
            info = await ps.join(s, uid, info.invite_code.lower())     # 소문자로 넣어도 된다
    assert info.member_count == 6
    async with db_session() as s:
        with pytest.raises(AppError):
            await ps.join(s, ids[6], info.invite_code)


async def test_한_사람에_한_파티(db_session):
    a = await _user(db_session, "a@t.kr")
    b = await _user(db_session, "b@t.kr")
    info = await _party(db_session, a)
    await _party(db_session, b)
    async with db_session() as s:
        with pytest.raises(AppError):
            await ps.join(s, b, info.invite_code)


async def test_인증과_전원_인증_3파이(db_session):
    a = await _user(db_session, "a@t.kr")
    b = await _user(db_session, "b@t.kr")
    info = await _party(db_session, a)
    async with db_session() as s:
        await ps.join(s, b, info.invite_code)
    async with db_session() as s:
        h = await ps.checkin(s, a)
        await ps.checkin(s, a)                                             # 두 번 눌러도 한 번
    assert h.today_remaining == 1 and not h.today_all_done
    assert h.members[0].is_leader and h.members[0].done_today and not h.members[1].done_today
    async with db_session() as s:
        h = await ps.checkin(s, b)
        await ps.checkin(s, b)
        pies = (await s.execute(select(PieLedger))).scalars().all()
    assert h.today_all_done and h.streak == 1
    assert sorted((p.user_id, p.delta) for p in pies) == sorted([(a, 3), (b, 3)])


async def test_N일_중_M일과_파티_연속_인증(db_session):
    a = await _user(db_session, "a@t.kr")
    b = await _user(db_session, "b@t.kr")
    info = await _party(db_session, a)
    async with db_session() as s:
        await ps.join(s, b, info.invite_code)
    y = today_kst() - timedelta(days=1)
    async with db_session() as s:                                         # 둘 다 어제 들어와서 어제 인증했다고 맞춘다
        for m in (await s.execute(select(PartyMember))).scalars():
            m.joined_on = y
        for uid in (a, b):
            s.add(PartyCheckin(party_id=info.party_id, user_id=uid, checkin_date=y, created_at=datetime(2026, 1, 1)))
        await s.commit()
    async with db_session() as s:
        await ps.checkin(s, a)
        h = await ps.checkin(s, b)
        c = await ps.card(s, info.party_id)
    assert h.streak == 2 and c.streak == 2 and c.name == "아침걷기"
    assert (h.members[0].days_total, h.members[0].days_done) == (2, 2)


async def test_오늘_들어온_사람은_어제_연속을_끊지_않는다(db_session):
    a = await _user(db_session, "a@t.kr")
    b = await _user(db_session, "b@t.kr")
    info = await _party(db_session, a)
    y = today_kst() - timedelta(days=1)
    async with db_session() as s:
        for m in (await s.execute(select(PartyMember))).scalars():
            m.joined_on = y
        s.add(PartyCheckin(party_id=info.party_id, user_id=a, checkin_date=y, created_at=datetime(2026, 1, 1)))
        await s.commit()
    async with db_session() as s:
        await ps.join(s, b, info.invite_code)                              # b는 오늘 들어옴
        h = await ps.home(s, a)
    assert h.streak == 1                                                   # 어제(a 혼자) 모두 인증 → 이어짐
    assert (h.members[1].days_total, h.members[1].days_done) == (1, 0)


async def test_모두_나가면_파티가_지워진다(db_session):
    a = await _user(db_session, "a@t.kr")
    b = await _user(db_session, "b@t.kr")
    info = await _party(db_session, a)
    async with db_session() as s:
        await ps.join(s, b, info.invite_code)
    async with db_session() as s:
        await ps.leave(s, a)                                               # 파티장이 나가면 b가 파티장
        h = await ps.home(s, b)
    assert h.members[0].is_me and h.members[0].is_leader
    async with db_session() as s:
        await ps.leave(s, b)
        assert await s.get(Party, info.party_id) is None