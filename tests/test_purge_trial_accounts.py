"""체험 이용자 정보 삭제 스크립트(app/scripts/purge_trial_accounts.py)."""
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, update

from app.core.config import settings
from app.models.access_log import AccessLog
from app.models.user import User, UserProfile
from app.scripts import purge_trial_accounts as purge
from tests.test_admin_overview import make_account

pytestmark = pytest.mark.asyncio


async def at(Session, uid: str, kst: datetime) -> None:
    async with Session() as s:
        await s.execute(update(User).where(User.user_id == uid).values(created_at=kst - timedelta(hours=9)))
        await s.commit()


@pytest_asyncio.fixture
async def accounts(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@team.kr")
    ids = {}
    for key, email, kst, status in [
        ("admin", "admin@team.kr", datetime(2026, 10, 22, 9), "active"),        # 팀원(관리자): 빠짐
        ("t1", "friend1@gmail.com", datetime(2026, 10, 22, 10), "active"),      # 체험 지인: 대상
        ("t2", "friend2@naver.com", datetime(2026, 10, 26, 16), "pending_guardian"),   # 체험 끝난 뒤 가입·보호자 대기도 대상
        ("demo", "demo-01@example.com", datetime(2026, 10, 23, 9), "active"),   # 남길 도메인: 빠짐
        ("early", "early@gmail.com", datetime(2026, 10, 20, 12), "active"),     # 체험 전 가입: 빠짐
        ("gone", "gone@gmail.com", datetime(2026, 10, 23, 12), "deleted"),      # 이미 탈퇴: 빠짐
    ]:
        _, uid = await make_account(db_session, email, status=status)
        await at(db_session, uid, kst)
        ids[key] = uid
    async with db_session() as s:
        s.add(AccessLog(account_id=ids["t1"], event="login", ip="1.2.3.4", created_at=datetime(2026, 10, 22, 2)))
        await s.commit()
    return ids


async def status_of(Session, uid):
    async with Session() as s:
        return (await s.execute(select(User.status).where(User.user_id == uid))).scalar_one()


async def test_미리보기는_대상만_보여_주고_이메일은_보이지_않는다(db_session, accounts, capsys):
    async with db_session() as s:
        code = await purge.run(s, date(2026, 10, 22), None, {"example.com"}, apply=False, confirm=None)
    out = capsys.readouterr().out
    assert code == 0 and "대상 2명" in out and "빠진 2명" in out
    assert accounts["t1"][-8:] in out and accounts["t2"][-8:] in out and accounts["demo"][-8:] not in out
    assert "friend1" not in out and "@" not in out.split("도메인별:")[1].split("\n", 1)[1]   # 목록에 이메일 없음
    assert await status_of(db_session, accounts["t1"]) == "active"                          # 미리보기는 안 지움


async def test_확인_인원이_다르면_아무것도_지우지_않는다(db_session, accounts):
    async with db_session() as s:
        code = await purge.run(s, date(2026, 10, 22), None, {"example.com"}, apply=True, confirm=3)
    assert code == 2
    assert await status_of(db_session, accounts["t1"]) == "active"


async def test_삭제하면_탈퇴와_같이_지우고_로그인_기록과_나머지는_남는다(db_session, accounts):
    async with db_session() as s:
        code = await purge.run(s, date(2026, 10, 22), None, {"example.com"}, apply=True, confirm=2)
    assert code == 0
    assert await status_of(db_session, accounts["t1"]) == "deleted"
    assert await status_of(db_session, accounts["t2"]) == "deleted"
    for keep in ("admin", "demo", "early"):
        assert await status_of(db_session, accounts[keep]) == "active"
    async with db_session() as s:
        assert (await s.execute(select(UserProfile).where(UserProfile.user_id == accounts["t1"]))).first() is None
        assert (await s.execute(select(AccessLog).where(AccessLog.account_id == accounts["t1"]))).first() is not None  # 3개월 보관


async def test_끝날짜를_주면_그날까지만(db_session, accounts, capsys):
    async with db_session() as s:
        await purge.run(s, date(2026, 10, 22), date(2026, 10, 25), set(), apply=False, confirm=None)
    out = capsys.readouterr().out
    assert "대상 2명" in out                      # t1 + demo(남길 도메인 안 줌), t2(10/26)는 빠짐
    assert accounts["t2"][-8:] not in out
