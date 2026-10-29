"""가입 횟수 제한: 같은 IP가 1시간 안에 SIGNUP_MAX_PER_IP번을 넘게 요청하면 잠시 막는다. 임시 예측 창구(/v1/predict)는 없다."""
from datetime import timedelta

import pytest

from app.core.config import settings
from app.services import login_guard
from tests.test_signup_consent import body, seed_policies

pytestmark = pytest.mark.asyncio


async def signup(client, ids, n, ip="203.0.113.50"):
    return await client.post("/v1/auth/signup", json=body(ids, email=f"u{n}@test.kr"), headers={"X-Forwarded-For": ip})


async def test_같은_IP가_한도를_넘게_가입하면_막힌다(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "SIGNUP_MAX_PER_IP", 3)
    ids = await seed_policies(db_session)
    assert [(await signup(client, ids, i)).status_code for i in range(3)] == [201, 201, 201]
    r = await signup(client, ids, 3)
    assert r.status_code == 429 and r.json()["error"]["code"] == "AUTH_SIGNUP_TOO_MANY"


async def test_이미_가입된_이메일을_반복해서_물어도_센다(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "SIGNUP_MAX_PER_IP", 2)
    ids = await seed_policies(db_session)
    assert (await signup(client, ids, 0)).status_code == 201
    assert (await signup(client, ids, 0)).status_code == 409           # 실패(중복)도 한 번으로 센다
    assert (await signup(client, ids, 0)).status_code == 429


async def test_다른_IP는_따로_센다(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "SIGNUP_MAX_PER_IP", 1)
    ids = await seed_policies(db_session)
    assert (await signup(client, ids, 0, ip="203.0.113.1")).status_code == 201
    assert (await signup(client, ids, 1, ip="203.0.113.2")).status_code == 201


async def test_1시간이_지나면_다시_가입할_수_있다(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "SIGNUP_MAX_PER_IP", 1)
    ids = await seed_policies(db_session)
    assert (await signup(client, ids, 0)).status_code == 201
    assert (await signup(client, ids, 1)).status_code == 429
    later = login_guard.utcnow() + timedelta(minutes=61)
    monkeypatch.setattr(login_guard, "utcnow", lambda: later)
    assert (await signup(client, ids, 1)).status_code == 201


async def test_임시_예측_창구는_없다(client):
    r = await client.post("/v1/predict", json={})
    assert r.status_code in (404, 405)
