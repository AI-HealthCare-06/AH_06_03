"""1:1 문의: 이용자가 남기고 관리자가 답하고, 이용자가 읽으면 빨간 점이 사라진다."""
from datetime import date

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.admin_audit import AdminAuditLog
from app.models.inquiry import Inquiry
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio

ADMIN = "admin@test.kr"


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)


async def make(Session, email: str) -> tuple[str, dict]:
    async with Session() as s:
        user = User(email=email, password_hash="x", status="active")
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        return user.user_id, {"Authorization": f"Bearer {create_access_token(user.user_id)}"}


async def test_문의_답변_읽음_흐름(client, db_session):
    _, user = await make(db_session, "u@test.kr")
    _, admin = await make(db_session, ADMIN)
    r = await client.post("/v1/inquiries", json={"title": "혈압 결과", "body": "수축기 150인데 괜찮나요?"}, headers=user)
    assert r.status_code == 201
    iid = r.json()["data"]["inquiry_id"]
    # 답이 오기 전: 안 읽은 답변 없음
    d = (await client.get("/v1/inquiries", headers=user)).json()["data"]
    assert d["unread"] == 0 and d["items"][0]["answered"] is False
    # 관리자: 미답변 목록 → 상세 → 답변
    assert (await client.get("/v1/admin/inquiries", params={"status": "open"}, headers=admin)).json()["data"]["total"] == 1
    det = (await client.get(f"/v1/admin/inquiries/{iid}", headers=admin)).json()["data"]
    assert det["body"].startswith("수축기") and "email" not in det
    assert (await client.put(f"/v1/admin/inquiries/{iid}/answer", json={"answer": "병원에 가 보세요."}, headers=admin)).status_code == 200
    # 이용자: 빨간 점 1 → 열어 보면 0
    d = (await client.get("/v1/inquiries", headers=user)).json()["data"]
    assert d["unread"] == 1 and d["items"][0]["answered"] is True and d["items"][0]["unread"] is True
    one = (await client.get(f"/v1/inquiries/{iid}", headers=user)).json()["data"]
    assert one["answer"] == "병원에 가 보세요."
    assert (await client.get("/v1/inquiries", headers=user)).json()["data"]["unread"] == 0
    # 관리자 행위 기록에는 번호만 남고 내용은 없다
    async with db_session() as s:
        logs = (await s.execute(select(AdminAuditLog.action, AdminAuditLog.target, AdminAuditLog.detail))).all()
    assert ("inquiry_answer", iid[-8:], None) in logs and all("수축기" not in (d or "") for _, _, d in logs)


async def test_남의_문의는_볼_수_없고_일반_사용자는_관리자_창구가_막힌다(client, db_session):
    _, a = await make(db_session, "a@test.kr")
    _, b = await make(db_session, "b@test.kr")
    iid = (await client.post("/v1/inquiries", json={"title": "t", "body": "b"}, headers=a)).json()["data"]["inquiry_id"]
    assert (await client.get(f"/v1/inquiries/{iid}", headers=b)).status_code == 404
    assert (await client.get("/v1/inquiries", headers=b)).json()["data"]["items"] == []
    assert (await client.get("/v1/admin/inquiries", headers=a)).status_code == 403
    assert (await client.put(f"/v1/admin/inquiries/{iid}/answer", json={"answer": "x"}, headers=a)).status_code == 403


async def test_빈_내용은_거절하고_답_없는_문의는_5개까지(client, db_session):
    _, u = await make(db_session, "u@test.kr")
    assert (await client.post("/v1/inquiries", json={"title": "  ", "body": "x"}, headers=u)).status_code == 422
    for n in range(5):
        assert (await client.post("/v1/inquiries", json={"title": f"t{n}", "body": "b"}, headers=u)).status_code == 201
    r = await client.post("/v1/inquiries", json={"title": "t6", "body": "b"}, headers=u)
    assert r.status_code == 429 and r.json()["error"]["code"] == "INQUIRY_LIMIT"


async def test_탈퇴하면_문의도_지워지고_건강정보_철회로는_남는다(client, db_session):
    from app.services import account_service
    uid, u = await make(db_session, "u@test.kr")
    await client.post("/v1/inquiries", json={"title": "t", "body": "b"}, headers=u)
    async with db_session() as s:
        await account_service.delete_health_data(s, uid)
        await s.commit()
    async with db_session() as s:
        assert len((await s.execute(select(Inquiry))).scalars().all()) == 1    # 철회로는 남는다
        user = await s.get(User, uid)
        await account_service._delete_user_rows(s, uid, account_service.KEEP_TABLES)   # 탈퇴가 쓰는 삭제
        await s.commit()
    async with db_session() as s:
        assert (await s.execute(select(Inquiry))).scalars().all() == []
