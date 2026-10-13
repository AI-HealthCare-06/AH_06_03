"""관리자 행위 기록 테스트 (REQ-ADM-005): 변경 기록, 열람 기록(중복 방지), 기록 보기, 권한, 탈퇴해도 남음."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, utcnow
from app.models.admin_audit import AdminAuditLog
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio

ADMIN = "admin@test.kr"


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)


async def make_account(Session, email: str) -> dict:
    async with Session() as s:
        user = User(email=email, password_hash="x", status="active")
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        return {"Authorization": f"Bearer {create_access_token(user.user_id)}"}


async def rows(Session) -> list[AdminAuditLog]:
    async with Session() as s:
        return list((await s.execute(select(AdminAuditLog).order_by(AdminAuditLog.created_at, AdminAuditLog.audit_id))).scalars())


async def ids(client, h) -> dict:
    cats = (await client.get("/v1/admin/challenges", headers=h)).json()["data"]
    return {"cat": {c["category_code"]: c["category_id"] for c in cats},
            "mission": {m["challenge_code"]: m["challenge_id"] for c in cats for m in c["missions"]}}


async def test_changes_are_recorded_with_before_and_after(client, db_session):
    h = await make_account(db_session, ADMIN)
    i = await ids(client, h)
    assert (await client.patch(f"/v1/admin/challenges/{i['mission']['NA-1']}", json={"active": False}, headers=h)).status_code == 200
    assert (await client.patch(f"/v1/admin/challenge-categories/{i['cat']['WEIGHT']}", json={"display_order": 1, "active": False}, headers=h)).status_code == 200
    changes = [r for r in await rows(db_session) if r.action.endswith("_update")]
    assert [(r.action, r.target, r.detail, r.actor_email) for r in changes] == [
        ("mission_update", "NA-1", "노출 켬→끔", ADMIN),
        ("category_update", "WEIGHT", "노출 켬→끔, 순서 7→1", ADMIN),
    ]
    assert all(r.created_at is not None for r in changes)


async def test_no_change_and_rejected_change_leave_no_record(client, db_session):
    h = await make_account(db_session, ADMIN)
    i = await ids(client, h)
    na1 = i["mission"]["NA-1"]
    assert (await client.patch(f"/v1/admin/challenges/{na1}", json={"active": True}, headers=h)).status_code == 200   # 이미 켜짐
    assert (await client.patch(f"/v1/admin/challenges/{i['mission']['SMK-1']}", json={"active": False}, headers=h)).status_code == 422
    assert [r for r in await rows(db_session) if r.action.endswith("_update")] == []


async def test_views_are_recorded_once_per_window(client, db_session):
    h = await make_account(db_session, ADMIN)
    for _ in range(3):
        await client.get("/v1/admin/challenges", headers=h)
        await client.get("/v1/admin/stats/challenges", headers=h)
    actions = [r.action for r in await rows(db_session)]
    assert actions.count("catalog_view") == 1 and actions.count("stats_view") == 1      # 새로고침마다 쌓이지 않음


async def test_view_is_recorded_again_after_the_window(client, db_session):
    h = await make_account(db_session, ADMIN)
    async with db_session() as s:
        s.add(AdminAuditLog(actor_email=ADMIN, action="catalog_view", created_at=utcnow() - timedelta(minutes=11)))
        await s.commit()
    await client.get("/v1/admin/challenges", headers=h)
    assert [r.action for r in await rows(db_session)].count("catalog_view") == 2


async def test_audit_log_endpoint_lists_newest_first_and_hides_internals(client, db_session):
    h = await make_account(db_session, ADMIN)
    i = await ids(client, h)
    await client.patch(f"/v1/admin/challenges/{i['mission']['NA-1']}", json={"active": False}, headers=h)
    await client.patch(f"/v1/admin/challenges/{i['mission']['NA-1']}", json={"active": True}, headers=h)
    r = await client.get("/v1/admin/audit-logs", headers=h)
    assert r.status_code == 200
    data = r.json()["data"]
    assert [d["detail"] for d in data if d["action"] == "mission_update"] == ["노출 끔→켬", "노출 켬→끔"]    # 최신순
    assert set(data[0]) == {"created_at", "actor_email", "action", "target", "detail"}                        # 번호·사용자 정보 없음
    assert len((await client.get("/v1/admin/audit-logs?limit=2", headers=h)).json()["data"]) == 2
    assert (await client.get("/v1/admin/audit-logs?limit=0", headers=h)).status_code == 422
    assert (await client.get("/v1/admin/audit-logs?limit=501", headers=h)).status_code == 422
    assert "audit_view" in [r.action for r in await rows(db_session)]                                         # 기록을 본 것도 기록


async def test_non_admin_cannot_read_and_leaves_no_trace(client, db_session):
    user = await make_account(db_session, "user@test.kr")
    assert (await client.get("/v1/admin/audit-logs", headers=user)).status_code == 403
    assert (await client.get("/v1/admin/audit-logs")).status_code == 401
    assert await rows(db_session) == []


async def test_records_survive_admin_withdrawal(client, db_session):
    """관리자가 탈퇴해도 기록은 남는다 (user_id 칸이 없어서 탈퇴 삭제 대상이 아니다)."""
    from app.services import account_service
    h = await make_account(db_session, ADMIN)
    await client.get("/v1/admin/challenges", headers=h)
    before = len(await rows(db_session))
    assert before == 1
    async with db_session() as s:
        admin = (await s.execute(select(User).where(User.email == ADMIN))).scalar_one()
        await account_service.delete_account_data(s, admin)
        await s.commit()
    assert len(await rows(db_session)) == before


async def test_audit_table_has_no_user_id_column():
    assert "user_id" not in AdminAuditLog.__table__.c      # 탈퇴 삭제·내 데이터 내려받기 대상에서 빠지는 이유
