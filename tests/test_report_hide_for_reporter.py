"""신고한 글·댓글은 신고한 사람의 목록에서 바로 빠진다. 다른 사람에게는 그대로 보인다."""
from datetime import date

import pytest

from app.core.config import settings
from app.core.security import create_access_token
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


async def feed_ids(client, h) -> list[str]:
    return [i["post_id"] for i in (await client.get("/v1/community/posts", headers=h)).json()["data"]["items"]]


async def test_신고한_글은_신고한_사람_목록에서만_빠진다(client, db_session):
    author = await make(client, db_session, "w@test.kr", "글쓴이")
    reporter = await make(client, db_session, "r@test.kr", "신고자")
    other = await make(client, db_session, "o@test.kr", "다른사람")
    bad = (await client.post("/v1/community/posts", json={"category": "tips", "title": "문제 글", "body": "x"}, headers=author)).json()["data"]["post_id"]
    ok = (await client.post("/v1/community/posts", json={"category": "tips", "title": "괜찮은 글", "body": "y"}, headers=author)).json()["data"]["post_id"]

    assert (await client.post(f"/v1/community/posts/{bad}/report", json={"reason": "spam"}, headers=reporter)).status_code == 201
    assert await feed_ids(client, reporter) == [ok]                     # 신고한 사람: 바로 빠짐
    assert (await client.get("/v1/community/posts", headers=reporter)).json()["data"]["total"] == 1
    assert set(await feed_ids(client, other)) == {bad, ok}              # 다른 사람: 그대로
    assert set(await feed_ids(client, author)) == {bad, ok}             # 작성자: 그대로
    assert (await client.get(f"/v1/community/posts/{bad}", headers=reporter)).status_code == 200   # 글을 여는 것은 막지 않음


async def test_문제_없음으로_처리돼도_신고한_사람에게는_계속_빠져_있다(client, db_session):
    admin = await make(client, db_session, ADMIN)
    author = await make(client, db_session, "w@test.kr", "글쓴이")
    reporter = await make(client, db_session, "r@test.kr", "신고자")
    pid = (await client.post("/v1/community/posts", json={"category": "tips", "title": "글", "body": "x"}, headers=author)).json()["data"]["post_id"]
    await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "other"}, headers=reporter)
    await client.post(f"/v1/admin/reports/post/{pid}/action", json={"action": "dismiss"}, headers=admin)
    assert await feed_ids(client, reporter) == []


async def test_신고한_댓글은_신고한_사람에게만_빠진다(client, db_session):
    author = await make(client, db_session, "w@test.kr", "글쓴이")
    reporter = await make(client, db_session, "r@test.kr", "신고자")
    other = await make(client, db_session, "o@test.kr", "다른사람")
    pid = (await client.post("/v1/community/posts", json={"category": "tips", "title": "글", "body": "x"}, headers=author)).json()["data"]["post_id"]
    bad = (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "광고 댓글"}, headers=other)).json()["data"]["comment_id"]
    await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "좋은 댓글"}, headers=author)
    await client.post(f"/v1/community/comments/{bad}/report", json={"reason": "spam"}, headers=reporter)
    mine = [c["body"] for c in (await client.get(f"/v1/community/posts/{pid}/comments", headers=reporter)).json()["data"]]
    theirs = [c["body"] for c in (await client.get(f"/v1/community/posts/{pid}/comments", headers=author)).json()["data"]]
    assert mine == ["좋은 댓글"] and theirs == ["광고 댓글", "좋은 댓글"]
