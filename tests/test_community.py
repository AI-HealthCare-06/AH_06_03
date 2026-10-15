"""커뮤니티: 닉네임, 글, 댓글, 좋아요, 파이 시작 선물과 글쓰기 보상, 동의 철회·탈퇴 때의 정리."""
from datetime import date

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.community import CommunityComment, CommunityLike, CommunityPost, CommunityProfile
from app.models.pie import PieLedger
from app.models.user import User, UserProfile
from app.services import account_service

pytestmark = pytest.mark.asyncio

ADMIN = "admin@test.kr"


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)


async def make(Session, email: str, nickname: str | None = None) -> tuple[str, dict]:
    async with Session() as s:
        user = User(email=email, password_hash="x", status="active")
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        uid, headers = user.user_id, {"Authorization": f"Bearer {create_access_token(user.user_id)}"}
    return uid, headers


async def with_nick(client, Session, email: str, nick: str) -> tuple[str, dict]:
    uid, h = await make(Session, email)
    assert (await client.put("/v1/community/me", json={"nickname": nick}, headers=h)).status_code == 200
    return uid, h


POST = {"category": "diet", "title": "국물 반만 먹기", "body": "건더기 먼저 먹고 국물은 한 숟갈만"}


async def test_닉네임을_처음_정하면_파이_10개를_받고_바꿀_때는_받지_않는다(client, db_session):
    _, h = await make(db_session, "a@test.kr")
    assert (await client.get("/v1/community/me", headers=h)).json()["data"] == {"nickname": None, "pie_gift": 0}
    r = (await client.put("/v1/community/me", json={"nickname": "걷는고양이"}, headers=h)).json()["data"]
    assert r == {"nickname": "걷는고양이", "pie_gift": 10}
    assert (await client.get("/v1/pie", headers=h)).json()["data"]["balance"] == 10
    r = (await client.put("/v1/community/me", json={"nickname": "초록접시"}, headers=h)).json()["data"]
    assert r["nickname"] == "초록접시" and r["pie_gift"] == 0
    assert (await client.get("/v1/pie", headers=h)).json()["data"]["balance"] == 10


async def test_닉네임_형식과_중복(client, db_session):
    _, a = await make(db_session, "a@test.kr")
    _, b = await make(db_session, "b@test.kr")
    for bad in ("가", "a" * 11, "me@test.kr", "닉 네임", "<b>x</b>"):
        assert (await client.put("/v1/community/me", json={"nickname": bad}, headers=a)).status_code == 422
    assert (await client.put("/v1/community/me", json={"nickname": "느린아침"}, headers=a)).status_code == 200
    r = await client.put("/v1/community/me", json={"nickname": "느린아침"}, headers=b)
    assert r.status_code == 409 and r.json()["error"]["code"] == "NICKNAME_TAKEN"
    assert (await client.put("/v1/community/me", json={"nickname": "느린아침"}, headers=a)).status_code == 200   # 내 닉네임은 그대로 다시 저장 가능


async def test_닉네임이_없으면_글_댓글_좋아요를_쓸_수_없다(client, db_session):
    _, a = await with_nick(client, db_session, "a@test.kr", "글쓴이")
    _, b = await make(db_session, "b@test.kr")
    pid = (await client.post("/v1/community/posts", json=POST, headers=a)).json()["data"]["post_id"]
    for call in (client.post("/v1/community/posts", json=POST, headers=b),
                 client.post(f"/v1/community/posts/{pid}/comments", json={"body": "hi"}, headers=b),
                 client.post(f"/v1/community/posts/{pid}/like", headers=b)):
        r = await call
        assert r.status_code == 409 and r.json()["error"]["code"] == "NICKNAME_REQUIRED"
    assert (await client.get("/v1/community/posts", headers=b)).status_code == 200     # 보기만 하는 건 닉네임 없이도 된다


async def test_글쓰기_보상은_하루_3번까지(client, db_session):
    _, h = await with_nick(client, db_session, "a@test.kr", "글쓴이")
    gains = [(await client.post("/v1/community/posts", json=POST, headers=h)).json()["data"]["pie_gain"] for _ in range(4)]
    assert gains == [2, 2, 2, 0]
    assert (await client.get("/v1/pie", headers=h)).json()["data"]["balance"] == 10 + 6
    hist = (await client.get("/v1/pie/history", params={"limit": 2}, headers=h)).json()["data"]
    assert hist["total"] == 4 and len(hist["items"]) == 2 and hist["balance"] == 16


async def test_목록_검색_카테고리_인기순(client, db_session):
    _, a = await with_nick(client, db_session, "a@test.kr", "글쓴이")
    _, b = await with_nick(client, db_session, "b@test.kr", "독자")
    p1 = (await client.post("/v1/community/posts", json={**POST, "title": "첫 글"}, headers=a)).json()["data"]["post_id"]
    p2 = (await client.post("/v1/community/posts", json={"category": "exercise", "title": "계단 오르기", "body": "세 층만"}, headers=a)).json()["data"]["post_id"]
    assert (await client.post(f"/v1/community/posts/{p1}/like", headers=b)).json()["data"] == {"liked": True, "like_count": 1}
    allp = (await client.get("/v1/community/posts", headers=b)).json()["data"]
    assert allp["total"] == 2 and [i["post_id"] for i in allp["items"]] == [p2, p1]          # 최신순
    pop = (await client.get("/v1/community/posts", params={"sort": "popular"}, headers=b)).json()["data"]
    assert [i["post_id"] for i in pop["items"]] == [p1, p2] and pop["items"][0]["liked_by_me"] is True
    assert (await client.get("/v1/community/posts", params={"category": "exercise"}, headers=b)).json()["data"]["total"] == 1
    found = (await client.get("/v1/community/posts", params={"q": "계단"}, headers=b)).json()["data"]
    assert [i["post_id"] for i in found["items"]] == [p2]
    assert found["items"][0]["author_nickname"] == "글쓴이" and found["items"][0]["mine"] is False
    assert (await client.get("/v1/community/posts", params={"category": "bad"}, headers=b)).status_code == 422
    # 좋아요 다시 누르면 취소
    assert (await client.post(f"/v1/community/posts/{p1}/like", headers=b)).json()["data"] == {"liked": False, "like_count": 0}


async def test_댓글과_삭제는_본인만(client, db_session):
    _, a = await with_nick(client, db_session, "a@test.kr", "글쓴이")
    _, b = await with_nick(client, db_session, "b@test.kr", "독자")
    pid = (await client.post("/v1/community/posts", json=POST, headers=a)).json()["data"]["post_id"]
    c = (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "저도 해볼게요"}, headers=b)).json()["data"]
    assert c["author_nickname"] == "독자" and c["mine"] is True
    got = (await client.get(f"/v1/community/posts/{pid}/comments", headers=a)).json()["data"]
    assert len(got) == 1 and got[0]["mine"] is False
    assert (await client.get("/v1/community/posts", headers=a)).json()["data"]["items"][0]["comment_count"] == 1
    assert (await client.delete(f"/v1/community/comments/{c['comment_id']}", headers=a)).status_code == 404   # 남의 댓글
    assert (await client.delete(f"/v1/community/posts/{pid}", headers=b)).status_code == 404                  # 남의 글
    assert (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "  "}, headers=b)).status_code == 422
    assert (await client.delete(f"/v1/community/comments/{c['comment_id']}", headers=b)).status_code == 204
    # 글을 지우면 딸린 좋아요·댓글도 함께 지워진다
    await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "다시"}, headers=b)
    await client.post(f"/v1/community/posts/{pid}/like", headers=b)
    assert (await client.delete(f"/v1/community/posts/{pid}", headers=a)).status_code == 204
    async with db_session() as s:
        assert (await s.execute(select(CommunityPost))).scalars().all() == []
        assert (await s.execute(select(CommunityComment))).scalars().all() == []
        assert (await s.execute(select(CommunityLike))).scalars().all() == []
    assert (await client.get(f"/v1/community/posts/{pid}", headers=b)).status_code == 404


async def test_로그인하지_않으면_쓸_수_없다(client, db_session):
    assert (await client.get("/v1/community/posts")).status_code == 401
    assert (await client.get("/v1/pie")).status_code == 401


async def test_동의_철회는_글과_닉네임은_남기고_파이는_지운다(client, db_session):
    uid, h = await with_nick(client, db_session, "a@test.kr", "글쓴이")
    await client.post("/v1/community/posts", json=POST, headers=h)
    async with db_session() as s:
        await account_service.delete_health_data(s, uid)
        await s.commit()
    async with db_session() as s:
        assert len((await s.execute(select(CommunityPost))).scalars().all()) == 1
        assert (await s.execute(select(CommunityProfile))).scalar_one().nickname == "글쓴이"
        assert (await s.execute(select(PieLedger))).scalars().all() == []
    assert (await client.get("/v1/pie", headers=h)).json()["data"]["balance"] == 0


async def test_탈퇴하면_커뮤니티_기록도_모두_지워진다(client, db_session):
    uid, h = await with_nick(client, db_session, "a@test.kr", "글쓴이")
    await client.post("/v1/community/posts", json=POST, headers=h)
    async with db_session() as s:
        await account_service.delete_account_data(s, await s.get(User, uid))
        await s.commit()
    async with db_session() as s:
        for model in (CommunityPost, CommunityProfile, PieLedger):
            assert (await s.execute(select(model))).scalars().all() == []
