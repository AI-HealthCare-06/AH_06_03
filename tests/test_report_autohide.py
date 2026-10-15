"""신고 누적 자동 숨김(서로 다른 3명), 하루 신고 10건 제한, 신고로 삭제한 글의 사진 삭제."""
from datetime import date

import pytest
from sqlalchemy import func, select

from app.apis.consent import require_health_consent
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.models.community import CommunityPostPhoto
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio

ADMIN = "admin@test.kr"
POST = {"category": "tips", "title": "신고될 글", "body": "본문"}
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)
    app.dependency_overrides[require_health_consent] = lambda: None   # 사진 올리기에 필요한 건강정보 동의는 여기선 통과
    yield
    app.dependency_overrides.pop(require_health_consent, None)


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


async def people(client, db_session, n: int) -> list[dict]:
    return [await make(client, db_session, f"r{i}@test.kr", f"신고자{i}") for i in range(n)]


async def new_post(client, h, title="신고될 글") -> str:
    return (await client.post("/v1/community/posts", json={**POST, "title": title}, headers=h)).json()["data"]["post_id"]


async def report(client, h, pid, reason="abuse"):
    return await client.post(f"/v1/community/posts/{pid}/report", json={"reason": reason}, headers=h)


async def visible_to(client, h, pid) -> bool:
    return (await client.get(f"/v1/community/posts/{pid}", headers=h)).status_code == 200


async def test_서로_다른_3명이_신고하면_자동으로_숨겨진다(client, db_session):
    admin = await make(client, db_session, ADMIN)
    author = await make(client, db_session, "w@test.kr", "글쓴이")
    r = await people(client, db_session, 4)
    pid = await new_post(client, author)

    for i in range(2):
        assert (await report(client, r[i], pid)).status_code == 201
    assert await visible_to(client, r[3], pid)                       # 2명까지는 그대로 보인다

    assert (await report(client, r[2], pid)).status_code == 201       # 3명째
    assert not await visible_to(client, r[3], pid)                    # 남에게는 안 보이고
    mine = (await client.get("/v1/community/posts", headers=author)).json()["data"]["items"][0]
    assert mine["hidden"] is True and mine["notice"]                  # 작성자에게는 숨김 안내가 보인다

    it = (await client.get("/v1/admin/reports", params={"status": "pending"}, headers=admin)).json()["data"]["items"][0]
    assert it["status"] == "pending" and it["auto_hidden"] is True and it["pending_count"] == 3


async def test_자동_숨김은_관리자가_문제_없음으로_처리하면_다시_보인다(client, db_session):
    admin = await make(client, db_session, ADMIN)
    author = await make(client, db_session, "w@test.kr", "글쓴이")
    r = await people(client, db_session, 4)
    pid = await new_post(client, author)
    for i in range(3):
        await report(client, r[i], pid)
    assert not await visible_to(client, r[3], pid)

    res = await client.post(f"/v1/admin/reports/post/{pid}/action", json={"action": "dismiss"}, headers=admin)
    assert res.status_code == 200 and res.json()["data"]["handled"] == 3
    assert await visible_to(client, r[3], pid)
    it = (await client.get("/v1/admin/reports", params={"status": "done"}, headers=admin)).json()["data"]["items"][0]
    assert it["auto_hidden"] is False and it["action"] == "dismiss"


async def test_자동_숨김을_관리자가_숨김으로_확정하면_계속_숨겨진다(client, db_session):
    admin = await make(client, db_session, ADMIN)
    author = await make(client, db_session, "w@test.kr", "글쓴이")
    r = await people(client, db_session, 4)
    pid = await new_post(client, author)
    for i in range(3):
        await report(client, r[i], pid)
    await client.post(f"/v1/admin/reports/post/{pid}/action", json={"action": "hide"}, headers=admin)
    assert not await visible_to(client, r[3], pid)


async def test_댓글도_3명이_신고하면_자동으로_숨겨진다(client, db_session):
    author = await make(client, db_session, "w@test.kr", "글쓴이")
    r = await people(client, db_session, 4)
    pid = await new_post(client, author)
    cid = (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "문제 댓글"}, headers=author)).json()["data"]["comment_id"]
    for i in range(3):
        assert (await client.post(f"/v1/community/comments/{cid}/report", json={"reason": "abuse"}, headers=r[i])).status_code == 201
    assert (await client.get(f"/v1/community/posts/{pid}/comments", headers=r[3])).json()["data"] == []


async def test_한_사람은_24시간에_10건까지만_신고할_수_있다(client, db_session):
    author = await make(client, db_session, "w@test.kr", "글쓴이")
    reporter = await make(client, db_session, "r@test.kr", "신고자")
    pids = [await new_post(client, author, f"글 {i}") for i in range(11)]
    for pid in pids[:10]:
        assert (await report(client, reporter, pid)).status_code == 201
    r = await report(client, reporter, pids[10])
    assert r.status_code == 429 and r.json()["error"]["code"] == "REPORT_DAILY_LIMIT"


async def test_신고로_삭제한_글의_사진도_지워진다(client, db_session):
    admin = await make(client, db_session, ADMIN)
    author = await make(client, db_session, "w@test.kr", "글쓴이")
    reporter = await make(client, db_session, "r@test.kr", "신고자")
    pid = await new_post(client, author)
    for extra in (b"1", b"2"):
        up = await client.post(f"/v1/community/posts/{pid}/photos", content=JPEG[:-2] + extra + JPEG[-2:],
                               headers={**author, "Content-Type": "image/jpeg"})
        assert up.status_code == 201
    await report(client, reporter, pid)
    await client.post(f"/v1/admin/reports/post/{pid}/action", json={"action": "delete"}, headers=admin)
    async with db_session() as s:
        n = (await s.execute(select(func.count()).select_from(CommunityPostPhoto)
                             .where(CommunityPostPhoto.post_id == pid))).scalar_one()
    assert n == 0
