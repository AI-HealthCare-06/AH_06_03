"""커뮤니티 신고: 이용자가 신고하고 관리자가 숨김·삭제·문제 없음으로 처리한다. 관리자 기록에는 번호만 남는다."""
from datetime import date

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.admin_audit import AdminAuditLog
from app.models.community import CommunityPost
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio

ADMIN = "admin@test.kr"
HEALTH_POST = {"category": "tips", "title": "제 혈압이 150인데 약 먹어도 될까요", "body": "어제 잰 혈압이 150/95였어요"}


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)


async def make(client, Session, email: str, nick: str | None = None) -> dict:
    async with Session() as s:
        user = User(email=email, password_hash="x", status="active")
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        h = {"Authorization": f"Bearer {create_access_token(user.user_id)}"}
    if nick:
        await client.put("/v1/community/me", json={"nickname": nick}, headers=h)
    return h


async def setup(client, db_session):
    admin = await make(client, db_session, ADMIN)
    author = await make(client, db_session, "w@test.kr", "걷는고양이")
    r1 = await make(client, db_session, "r1@test.kr", "신고자일")
    r2 = await make(client, db_session, "r2@test.kr", "신고자이")
    pid = (await client.post("/v1/community/posts", json=HEALTH_POST, headers=author)).json()["data"]["post_id"]
    return admin, author, r1, r2, pid


async def test_신고_목록은_글별로_묶고_사유별_건수를_보여_준다(client, db_session):
    admin, author, r1, r2, pid = await setup(client, db_session)
    assert (await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "health_info"}, headers=r1)).status_code == 201
    assert (await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "spam"}, headers=r2)).status_code == 201
    d = (await client.get("/v1/admin/reports", params={"status": "pending"}, headers=admin)).json()["data"]
    assert d["total"] == 1 and d["pending_total"] == 1
    it = d["items"][0]
    assert (it["target_type"], it["target_id"], it["report_count"], it["pending_count"]) == ("post", pid, 2, 2)
    assert it["reasons"] == {"health_info": 1, "spam": 1} and it["author_nickname"] == "걷는고양이"
    assert it["category"] == "tips" and it["title"] == HEALTH_POST["title"] and it["preview"].startswith("어제 잰 혈압")
    assert it["status"] == "pending" and it["action"] is None
    assert (await client.get("/v1/admin/reports", params={"status": "done"}, headers=admin)).json()["data"]["total"] == 0


async def test_숨기기_처리하면_남의_목록에서는_사라지고_작성자에게는_안내가_보인다(client, db_session):
    admin, author, r1, r2, pid = await setup(client, db_session)
    await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "health_info"}, headers=r1)
    res = (await client.post(f"/v1/admin/reports/post/{pid}/action", json={"action": "hide"}, headers=admin)).json()["data"]
    assert res == {"target_type": "post", "target_id": pid, "action": "hide", "handled": 1}
    assert (await client.get("/v1/community/posts", headers=r1)).json()["data"]["total"] == 0
    assert (await client.get(f"/v1/community/posts/{pid}", headers=r1)).status_code == 404
    mine = (await client.get("/v1/community/posts", headers=author)).json()["data"]["items"][0]
    assert mine["hidden"] is True and mine["notice"] == "운영 정책에 따라 숨김 처리됐어요" and mine["preview"] == ""
    assert (await client.get(f"/v1/community/posts/{pid}", headers=author)).json()["data"]["body"] == ""
    # 처리한 뒤에는 처리 완료 목록으로 간다
    done = (await client.get("/v1/admin/reports", params={"status": "done"}, headers=admin)).json()["data"]
    assert done["total"] == 1 and done["pending_total"] == 0 and done["items"][0]["action"] == "hide"
    # 숨긴 글은 좋아요·신고·댓글을 더 받지 않는다
    assert (await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "spam"}, headers=r2)).status_code == 404
    assert (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "x"}, headers=r2)).status_code == 404
    # 이미 처리한 신고는 다시 처리할 수 없다
    r = await client.post(f"/v1/admin/reports/post/{pid}/action", json={"action": "delete"}, headers=admin)
    assert r.status_code == 409 and r.json()["error"]["code"] == "REPORT_ALREADY_HANDLED"


async def test_삭제하면_내용이_비워지고_문제_없음이면_그대로_보인다(client, db_session):
    admin, author, r1, r2, pid = await setup(client, db_session)
    ok = (await client.post("/v1/community/posts", json={"category": "diet", "title": "괜찮은 글", "body": "문제 없어요"},
                            headers=author)).json()["data"]["post_id"]
    await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "health_info"}, headers=r1)
    await client.post(f"/v1/community/posts/{ok}/report", json={"reason": "other"}, headers=r1)
    await client.post(f"/v1/admin/reports/post/{pid}/action", json={"action": "delete"}, headers=admin)
    await client.post(f"/v1/admin/reports/post/{ok}/action", json={"action": "dismiss"}, headers=admin)
    async with db_session() as s:
        p = await s.get(CommunityPost, pid)
        assert (p.status, p.title, p.body) == ("deleted", "(삭제됨)", "")
    assert (await client.get(f"/v1/community/posts/{pid}", headers=author)).status_code == 404         # 삭제는 작성자에게도 안 보인다
    assert (await client.get(f"/v1/community/posts/{ok}", headers=r2)).status_code == 200              # 문제 없음: 그대로 보임
    done = {i["target_id"]: i["action"] for i in (await client.get("/v1/admin/reports", params={"status": "done"}, headers=admin)).json()["data"]["items"]}
    assert done == {pid: "delete", ok: "dismiss"}


async def test_댓글_신고와_처리(client, db_session):
    admin, author, r1, r2, pid = await setup(client, db_session)
    cid = (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "광고 아닌 척하는 댓글"}, headers=r2)).json()["data"]["comment_id"]
    assert (await client.post(f"/v1/community/comments/{cid}/report", json={"reason": "spam"}, headers=r1)).status_code == 201
    it = (await client.get("/v1/admin/reports", headers=admin)).json()["data"]["items"][0]
    assert (it["target_type"], it["target_id"], it["preview"]) == ("comment", cid, "광고 아닌 척하는 댓글")
    assert it["author_nickname"] == "신고자이" and it["title"] == HEALTH_POST["title"]       # 제목은 달린 글의 제목
    await client.post(f"/v1/admin/reports/comment/{cid}/action", json={"action": "hide"}, headers=admin)
    assert (await client.get(f"/v1/community/posts/{pid}/comments", headers=r1)).json()["data"] == []


async def test_신고_규칙_중복_본인_잘못된_사유(client, db_session):
    admin, author, r1, r2, pid = await setup(client, db_session)
    assert (await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "abuse"}, headers=r1)).status_code == 201
    dup = await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "spam"}, headers=r1)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "ALREADY_REPORTED"
    own = await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "spam"}, headers=author)
    assert own.status_code == 400 and own.json()["error"]["code"] == "REPORT_OWN"
    assert (await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "bad"}, headers=r2)).status_code == 422
    assert (await client.post("/v1/community/posts/none/report", json={"reason": "spam"}, headers=r2)).status_code == 404


async def test_관리자만_쓸_수_있고_기록에는_번호만_남는다(client, db_session):
    admin, author, r1, r2, pid = await setup(client, db_session)
    await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "health_info"}, headers=r1)
    assert (await client.get("/v1/admin/reports", headers=r1)).status_code == 403
    assert (await client.post(f"/v1/admin/reports/post/{pid}/action", json={"action": "hide"}, headers=r1)).status_code == 403
    assert (await client.post(f"/v1/admin/reports/post/{pid}/action", json={"action": "bad"}, headers=admin)).status_code == 422
    assert (await client.post("/v1/admin/reports/video/x/action", json={"action": "hide"}, headers=admin)).status_code == 404
    await client.get("/v1/admin/reports", headers=admin)
    await client.post(f"/v1/admin/reports/post/{pid}/action", json={"action": "hide"}, headers=admin)
    async with db_session() as s:
        logs = (await s.execute(select(AdminAuditLog.action, AdminAuditLog.target, AdminAuditLog.detail))).all()
    assert ("community_reports_view", None, None) in logs
    assert ("community_report_hide", f"p-{pid[-8:]}", None) in logs
    assert all("혈압" not in (t or "") and "혈압" not in (d or "") for _, t, d in logs)
