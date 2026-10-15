"""한 계정은 한 기기에서만: 새로 로그인하면 다른 기기의 로그인이 바로 끊긴다."""
from datetime import datetime

import pytest

from app.core.security import create_access_token, hash_password
from app.models.user import User, UserProfile
from app.services import admin_users_service

pytestmark = pytest.mark.asyncio
EMAIL, PW = "one@test.kr", "password1"


async def make_login_user(Session):
    async with Session() as s:
        u = User(email=EMAIL, password_hash=hash_password(PW), status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=datetime(1985, 5, 5).date()))
        await s.commit()
        return u.user_id


async def login(client):
    r = await client.post("/v1/auth/login", json={"email": EMAIL, "password": PW})
    assert r.status_code == 200
    d = r.json()["data"]
    return d["access_token"], d["refresh_token"]


async def me(client, access):
    return await client.get("/v1/users/me", headers={"Authorization": f"Bearer {access}"})


async def refresh(client, token):
    return await client.post("/v1/auth/token/refresh", json={"refresh_token": token})


async def test_second_login_ends_first_device(client, db_session):
    await make_login_user(db_session)
    a_access, a_refresh = await login(client)        # 기기 A
    b_access, b_refresh = await login(client)        # 기기 B

    r = await me(client, a_access)                   # A의 팔찌는 30분이 안 지났어도 바로 막힌다
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_SESSION_ENDED"
    assert (await refresh(client, a_refresh)).status_code == 401   # A의 쿠폰으로 다시 받을 수도 없다

    assert (await me(client, b_access)).status_code == 200
    assert (await refresh(client, b_refresh)).status_code == 200


async def test_failed_login_does_not_end_other_device(client, db_session):
    await make_login_user(db_session)
    access, _ = await login(client)
    r = await client.post("/v1/auth/login", json={"email": EMAIL, "password": "wrong-pass"})
    assert r.status_code == 401
    assert (await me(client, access)).status_code == 200   # 비밀번호를 틀린 시도로는 남을 끊지 못한다


async def test_refreshed_token_keeps_working(client, db_session):
    await make_login_user(db_session)
    _, first_refresh = await login(client)
    r = await refresh(client, first_refresh)
    assert r.status_code == 200
    new_access = r.json()["data"]["access_token"]
    assert (await me(client, new_access)).status_code == 200


async def test_logout_ends_token_immediately(client, db_session):
    await make_login_user(db_session)
    access, refresh_token = await login(client)
    r = await client.post("/v1/auth/logout", json={"refresh_token": refresh_token},
                          headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 204
    assert (await me(client, access)).status_code == 401


async def test_token_without_session_id_still_accepted(client, db_session):
    uid = await make_login_user(db_session)          # 이 기능 전에 발급된 팔찌(최대 30분)와 시험용 팔찌
    assert (await me(client, create_access_token(uid))).status_code == 200


async def test_suspend_logs_out_every_device(client, db_session):
    uid = await make_login_user(db_session)
    access, refresh_token = await login(client)
    async with db_session() as s:
        await admin_users_service.suspend(s, "admin@test.kr", uid, 3)
    r = await me(client, access)
    assert r.status_code == 403 and r.json()["error"]["code"] == "ACCOUNT_SUSPENDED"
    assert (await refresh(client, refresh_token)).status_code == 401   # 정지와 함께 쿠폰도 끊겼다
