"""신고 처리에서 쓰는 회원 조치: 이용 정지(기간·무기한), 정지 해제, 계정 삭제. 관리자 계정은 건드릴 수 없다."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, utcnow
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio

ADMIN = "admin@test.kr"


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)


async def make(Session, email):
    async with Session() as s:
        u = User(email=email, password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        return u.user_id, {"Authorization": f"Bearer {create_access_token(u.user_id)}"}


async def test_정지하면_이미_받은_로그인으로도_막히고_해제하면_다시_쓸_수_있다(client, db_session):
    _, admin = await make(db_session, ADMIN)
    uid, h = await make(db_session, "u@t.kr")
    assert (await client.get("/v1/community/me", headers=h)).status_code == 200
    assert (await client.post(f"/v1/admin/users/{uid}/suspend", json={"days": 7}, headers=h)).status_code == 403   # 관리자만
    assert (await client.post(f"/v1/admin/users/{uid}/suspend", json={"days": 7}, headers=admin)).status_code == 204
    r = await client.get("/v1/community/me", headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "ACCOUNT_SUSPENDED"
    row = (await client.get("/v1/admin/users", headers=admin)).json()["data"]["items"]
    assert [x["suspended_until"] is not None for x in row if x["user_id"] == uid] == [True]
    assert (await client.post(f"/v1/admin/users/{uid}/unsuspend", headers=admin)).status_code == 204
    assert (await client.get("/v1/community/me", headers=h)).status_code == 200


async def test_정지_기간이_지나면_저절로_풀리고_무기한은_안_풀린다(client, db_session):
    _, admin = await make(db_session, ADMIN)
    uid, h = await make(db_session, "u@t.kr")
    await client.post(f"/v1/admin/users/{uid}/suspend", json={}, headers=admin)               # 무기한
    assert (await client.get("/v1/community/me", headers=h)).status_code == 403
    async with db_session() as s:
        (await s.get(User, uid)).suspended_until = utcnow() - timedelta(minutes=1)            # 기간이 끝났다
        await s.commit()
    assert (await client.get("/v1/community/me", headers=h)).status_code == 200


async def test_회원을_삭제하고_관리자_계정은_조치할_수_없다(client, db_session):
    aid, admin = await make(db_session, ADMIN)
    uid, h = await make(db_session, "u@t.kr")
    assert (await client.delete(f"/v1/admin/users/{aid}", headers=admin)).status_code == 409
    assert (await client.post(f"/v1/admin/users/{aid}/suspend", json={"days": 1}, headers=admin)).status_code == 409
    assert (await client.delete(f"/v1/admin/users/{uid}", headers=admin)).status_code == 204
    async with db_session() as s:
        assert (await s.get(User, uid)).status == "deleted"
    assert (await client.get("/v1/community/me", headers=h)).status_code == 401              # 삭제된 계정은 로그인 풀림
    assert (await client.delete(f"/v1/admin/users/{uid}", headers=admin)).status_code == 404
