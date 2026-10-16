"""관리자 글 관리 (신고 없이): 전체 글 목록(최신순·검색·상태·파티 글 제외·열람 기록), 숨김·삭제·다시 보이기."""
from datetime import date, datetime

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.admin_audit import AdminAuditLog
from app.models.community import CommunityPost
from app.models.party import Party
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio

ADMIN = "admin@test.kr"


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


async def write(client, h, title, body="본문입니다"):
    r = await client.post("/v1/community/posts", json={"category": "tips", "title": title, "body": body}, headers=h)
    return r.json()["data"]["post_id"]


async def setup(client, db_session):
    admin = await make(client, db_session, ADMIN)
    author = await make(client, db_session, "w@test.kr", "걷는고양이")
    return admin, author


async def test_관리자만_볼_수_있다(client, db_session):
    _, author = await setup(client, db_session)
    assert (await client.get("/v1/admin/community/posts", headers=author)).status_code == 403


async def test_전체_글_최신순_검색_상태_필터(client, db_session):
    admin, author = await setup(client, db_session)
    p1 = await write(client, author, "첫 글 걷기 후기")
    p2 = await write(client, author, "둘째 글", body="국물 남기기 성공")
    d = (await client.get("/v1/admin/community/posts", headers=admin)).json()["data"]
    assert d["total"] == 2 and [i["post_id"] for i in d["items"]] == [p2, p1]          # 최신순
    it = d["items"][0]
    assert it["author_nickname"] == "걷는고양이" and it["status"] == "visible" and it["author_user_id"]
    d = (await client.get("/v1/admin/community/posts", params={"q": "국물"}, headers=admin)).json()["data"]
    assert [i["post_id"] for i in d["items"]] == [p2]                                     # 본문 검색
    await client.post(f"/v1/admin/community/posts/{p1}/action", json={"action": "hide"}, headers=admin)
    d = (await client.get("/v1/admin/community/posts", params={"status": "hidden"}, headers=admin)).json()["data"]
    assert [i["post_id"] for i in d["items"]] == [p1]


async def test_검색어의_퍼센트는_글자_그대로(client, db_session):
    admin, author = await setup(client, db_session)
    await write(client, author, "할인 50% 받았어요")
    await write(client, author, "아무 글")
    d = (await client.get("/v1/admin/community/posts", params={"q": "%"}, headers=admin)).json()["data"]
    assert d["total"] == 1


async def test_파티_글은_목록에_없고_관리도_안_된다(client, db_session):
    admin, author = await setup(client, db_session)
    await write(client, author, "전체 글")
    pid = await write(client, author, "파티 글")
    async with db_session() as s:                          # 파티 글로 바꾼다
        party = Party(name="아침걷기", invite_code="PAEON-TEST", challenge_code="ACT-2",
                      started_on=date(2026, 10, 1), created_at=datetime(2026, 10, 1))
        s.add(party)
        await s.flush()
        (await s.get(CommunityPost, pid)).party_id = party.party_id
        await s.commit()
    d = (await client.get("/v1/admin/community/posts", headers=admin)).json()["data"]
    assert d["total"] == 1 and d["items"][0]["title"] == "전체 글"
    res = await client.post(f"/v1/admin/community/posts/{pid}/action", json={"action": "hide"}, headers=admin)
    assert res.status_code == 404


async def test_신고_없이_숨김_다시보이기_삭제(client, db_session):
    admin, author = await setup(client, db_session)
    pid = await write(client, author, "비속어가 섞인 글", body="필터에 안 걸린 나쁜 말")
    r = (await client.post(f"/v1/admin/community/posts/{pid}/action", json={"action": "hide"}, headers=admin)).json()["data"]
    assert r == {"post_id": pid, "status": "hidden", "handled_reports": 0}
    other = await make(client, db_session, "o@test.kr", "구경꾼")
    assert all(p["post_id"] != pid for p in (await client.get("/v1/community/posts", headers=other)).json()["data"]["items"])
    r = (await client.post(f"/v1/admin/community/posts/{pid}/action", json={"action": "restore"}, headers=admin)).json()["data"]
    assert r["status"] == "visible"
    r = (await client.post(f"/v1/admin/community/posts/{pid}/action", json={"action": "delete"}, headers=admin)).json()["data"]
    assert r["status"] == "deleted"
    async with db_session() as s:
        post = await s.get(CommunityPost, pid)
        assert (post.title, post.body) == ("(삭제됨)", "")
    res = await client.post(f"/v1/admin/community/posts/{pid}/action", json={"action": "restore"}, headers=admin)
    assert res.status_code == 409 and res.json()["error"]["code"] == "COMMUNITY_ALREADY_DELETED"


async def test_대기_신고가_있으면_함께_처리된다(client, db_session):
    admin, author = await setup(client, db_session)
    reporter = await make(client, db_session, "r@test.kr", "신고자")
    pid = await write(client, author, "신고된 글")
    await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "spam"}, headers=reporter)
    r = (await client.post(f"/v1/admin/community/posts/{pid}/action", json={"action": "delete"}, headers=admin)).json()["data"]
    assert r["handled_reports"] == 1
    d = (await client.get("/v1/admin/reports", params={"status": "pending"}, headers=admin)).json()["data"]
    assert d["pending_total"] == 0


async def test_열람과_조치가_관리자_기록에_남는다(client, db_session):
    admin, author = await setup(client, db_session)
    pid = await write(client, author, "기록 확인")
    await client.get("/v1/admin/community/posts", headers=admin)
    await client.get("/v1/admin/community/posts", headers=admin)          # 10분 안에 다시 열면 한 번만
    await client.post(f"/v1/admin/community/posts/{pid}/action", json={"action": "hide"}, headers=admin)
    async with db_session() as s:
        actions = [a.action for a in (await s.execute(select(AdminAuditLog))).scalars()]
    assert actions.count("community_posts_view") == 1 and "community_post_hide" in actions