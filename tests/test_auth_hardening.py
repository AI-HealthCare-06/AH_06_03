"""인증·계정 보안 보완 (이슈 #146, API 보안 검사 1묶음). 서명 키 기본값 검사는 #152(test_required_secrets.py)."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update

from app.core.security import hash_password
from app.models.user import User, UserProfile, UserSession

pytestmark = pytest.mark.asyncio
EMAIL, PW = "safe@test.kr", "password1"


async def make_user(Session) -> str:
    async with Session() as s:
        u = User(email=EMAIL, password_hash=hash_password(PW), status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1985, 5, 5)))
        await s.commit()
        return u.user_id


async def login(client) -> dict:
    r = await client.post("/v1/auth/login", json={"email": EMAIL, "password": PW})
    assert r.status_code == 200
    return r.json()["data"]


async def test_탈퇴_비밀번호는_여러_번_틀리면_잠시_막힌다(client, db_session):
    await make_user(db_session)
    h = {"Authorization": f"Bearer {(await login(client))['access_token']}"}
    for _ in range(5):
        r = await client.post("/v1/users/me/deletion-requests", json={"password": "wrong-pass"}, headers=h)
        assert r.status_code == 401
    r = await client.post("/v1/users/me/deletion-requests", json={"password": PW}, headers=h)
    assert r.status_code == 429                                         # 맞는 비밀번호라도 잠시 막힘
    async with db_session() as s:
        assert (await s.execute(select(User.status))).scalar_one() == "active"   # 계정은 그대로


async def test_탈퇴하면_세션이_지워져_재발급이_안_된다(client, db_session):
    await make_user(db_session)
    tokens = await login(client)
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.post("/v1/users/me/deletion-requests", json={"password": PW}, headers=h)).status_code == 201
    r = await client.post("/v1/auth/token/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401
    async with db_session() as s:
        assert (await s.execute(select(func.count()).select_from(UserSession))).scalar_one() == 0


async def test_정지된_계정은_재발급을_받지_못한다(client, db_session):
    uid = await make_user(db_session)
    tokens = await login(client)
    async with db_session() as s:                                       # 세션을 끊지 않고 정지만 된 경우를 만든다
        await s.execute(update(User).where(User.user_id == uid).values(
            suspended_until=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=3)))
        await s.commit()
    r = await client.post("/v1/auth/token/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


async def test_이용할_수_없는_계정은_재발급을_받지_못한다(client, db_session):
    uid = await make_user(db_session)
    tokens = await login(client)
    async with db_session() as s:                                       # 세션은 남아 있는데 계정만 바뀐 경우
        await s.execute(update(User).where(User.user_id == uid).values(status="pending_guardian"))
        await s.commit()
    r = await client.post("/v1/auth/token/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401
