"""로그인 시도 제한: 같은 이메일 15분 안 5번, 같은 IP 15분 안 20번 틀리면 잠시 막는다.
실패 횟수는 메모리에만 두고 접속 기록(DB)에는 남기지 않는다."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password, utcnow
from app.services import login_guard
from app.models.access_log import AccessLog
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio
EMAIL, PW = "lim@test.kr", "password1"


async def make_user(Session, email=EMAIL):
    async with Session() as s:
        u = User(email=email, password_hash=hash_password(PW), status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=datetime(1985, 5, 5).date()))
        await s.commit()
        return u.user_id


async def login(client, email=EMAIL, pw=PW, ip="203.0.113.10"):
    return await client.post("/v1/auth/login", json={"email": email, "password": pw},
                             headers={"X-Forwarded-For": ip})


async def test_같은_이메일로_5번_틀리면_맞는_비밀번호도_잠시_막힌다(client, db_session):
    await make_user(db_session)
    for _ in range(5):
        assert (await login(client, pw="wrong-pass")).status_code == 401
    r = await login(client)                                             # 맞는 비밀번호라도
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "AUTH_TOO_MANY_ATTEMPTS"
    assert "15분" in r.json()["error"]["message"]


async def test_로그인에_성공하면_틀린_횟수를_처음부터_다시_센다(client, db_session):
    await make_user(db_session)
    for _ in range(4):
        await login(client, pw="wrong-pass")
    assert (await login(client)).status_code == 200
    for _ in range(4):
        assert (await login(client, pw="wrong-pass")).status_code == 401   # 아직 5번이 안 됐으므로 401
    assert (await login(client)).status_code == 200


async def test_15분이_지나면_다시_로그인할_수_있다(client, db_session, monkeypatch):
    await make_user(db_session)
    for _ in range(5):
        await login(client, pw="wrong-pass")
    assert (await login(client)).status_code == 429
    later = utcnow() + timedelta(minutes=16)
    monkeypatch.setattr(login_guard, "utcnow", lambda: later)        # 16분 뒤
    assert (await login(client)).status_code == 200


async def test_막혀_있는_동안의_시도는_실패로_세지_않는다(client, db_session):
    await make_user(db_session)
    for _ in range(5):
        await login(client, pw="wrong-pass")
    for _ in range(3):
        assert (await login(client, pw="wrong-pass")).status_code == 429
    assert len(login_guard._by_email[EMAIL]) == 5                      # 막힌 3번은 세지 않아 막힘이 늘어나지 않는다


async def test_없는_이메일도_똑같이_막혀서_가입_여부를_알_수_없다(client, db_session):
    for _ in range(5):
        assert (await login(client, email="nobody@test.kr", pw="wrong-pass")).status_code == 401
    assert (await login(client, email="nobody@test.kr", pw="wrong-pass")).status_code == 429


async def test_같은_IP에서_여러_계정을_한도만큼_틀리면_그_IP는_막힌다(client, db_session):
    await make_user(db_session)
    limit = settings.LOGIN_MAX_FAILS_PER_IP
    for i in range(limit):                                              # 계정마다 1번씩, 한도만큼의 계정
        assert (await login(client, email=f"spray{i}@test.kr", pw="wrong-pass")).status_code == 401
    assert (await login(client)).status_code == 429                     # 같은 IP: 진짜 계정도 막힘
    assert (await login(client, ip="198.51.100.7")).status_code == 200  # 다른 IP는 그대로


async def test_같은_와이파이에서_20명이_한_번씩_틀려도_막히지_않는다(client, db_session):
    await make_user(db_session)
    for i in range(20):
        assert (await login(client, email=f"guest{i}@test.kr", pw="wrong-pass")).status_code == 401
    assert (await login(client)).status_code == 200                     # 기본 한도(50)라 같은 자리의 다른 사람은 그대로 로그인


async def test_IP_한도는_설정으로_바꿀_수_있다(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILS_PER_IP", 3)
    await make_user(db_session)
    for i in range(3):
        await login(client, email=f"x{i}@test.kr", pw="wrong-pass")
    assert (await login(client)).status_code == 429


async def test_실패는_접속_기록에_남지_않는다(client, db_session):
    await make_user(db_session)
    for _ in range(5):
        await login(client, pw="wrong-pass", ip="203.0.113.99")
    await login(client, ip="203.0.113.99")                              # 막힌 시도도
    async with db_session() as s:
        assert (await s.execute(select(AccessLog))).scalars().all() == []
