"""서비스 접속(로그인) 기록과 관리자 권한 부여·회수 기록."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password, utcnow
from app.models.access_log import AccessLog
from app.models.admin_audit import AdminAuditLog
from app.models.user import User, UserProfile
from app.services import admin_registry_service

pytestmark = pytest.mark.asyncio


async def make_login_user(Session, email="a@test.kr"):
    async with Session() as s:
        u = User(email=email, password_hash=hash_password("password1"), status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=datetime(1985, 5, 5).date()))
        await s.commit()
        return u.user_id


async def test_login_records_ip_and_purges_old(client, db_session):
    uid = await make_login_user(db_session)
    async with db_session() as s:    # 94일 전 기록 하나
        s.add(AccessLog(account_id=uid, event="login", ip="1.1.1.1", created_at=utcnow() - timedelta(days=94)))
        s.add(AccessLog(account_id=uid, event="login", ip="2.2.2.2", created_at=utcnow() - timedelta(days=30)))
        await s.commit()
    r = await client.post("/v1/auth/login", json={"email": "a@test.kr", "password": "password1"},
                          headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"})
    assert r.status_code == 200
    async with db_session() as s:
        ips = sorted(a.ip for a in (await s.execute(select(AccessLog))).scalars().all())
    assert ips == ["2.2.2.2", "203.0.113.7"]      # 94일 전 기록은 지워지고 새 기록이 남는다


async def test_failed_login_leaves_no_record(client, db_session):
    await make_login_user(db_session)
    r = await client.post("/v1/auth/login", json={"email": "a@test.kr", "password": "wrong-pass"})
    assert r.status_code == 401
    async with db_session() as s:
        assert (await s.execute(select(AccessLog))).scalars().all() == []


async def test_admin_grant_and_revoke_are_logged_once(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "a@x.kr,b@x.kr")
    async with db_session() as s:
        assert await admin_registry_service.sync_admin_log(s) == (["a@x.kr", "b@x.kr"], [])
    async with db_session() as s:                    # 같은 상태로 다시 켜져도 새 기록은 없다
        assert await admin_registry_service.sync_admin_log(s) == ([], [])
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "a@x.kr")
    async with db_session() as s:
        assert await admin_registry_service.sync_admin_log(s) == ([], ["b@x.kr"])
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "a@x.kr,b@x.kr")   # 다시 넣으면 다시 부여로 남는다
    async with db_session() as s:
        assert await admin_registry_service.sync_admin_log(s) == (["b@x.kr"], [])
    async with db_session() as s:
        rows = (await s.execute(select(AdminAuditLog.action, AdminAuditLog.target))).all()
    assert sorted(rows) == [("admin_granted", "a@x.kr"), ("admin_granted", "b@x.kr"), ("admin_granted", "b@x.kr"), ("admin_revoked", "b@x.kr")]
