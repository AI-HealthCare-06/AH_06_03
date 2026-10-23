"""이벤트 알림: 댓글(글쓴이), 답글(원 댓글 쓴 사람), 문의 답변(문의한 사람), 파티 참여(기존 멤버). 본인 일은 본인에게 안 보낸다."""
import json
from datetime import date, datetime

import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.models.inquiry import Inquiry
from app.models.push import PushSubscription
from app.models.user import User, UserProfile
from app.services import inquiry_service, notify_service, party_service, push_service

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 10, 21, 3, 0)


@pytest.fixture(autouse=True)
def sent(monkeypatch):
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", "test-key")
    box = []
    monkeypatch.setattr(push_service, "_webpush", lambda sub, payload: box.append((sub.user_id, json.loads(payload))))
    return box


async def _user(client, Session, email, nick=None, subscribed=True):
    async with Session() as s:
        u = User(email=email, password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1990, 1, 1)))
        if subscribed:
            s.add(PushSubscription(user_id=u.user_id, endpoint=f"https://push.example.com/{email}", p256dh="p", auth="a", created_at=NOW))
        await s.commit()
        h = {"Authorization": f"Bearer {create_access_token(u.user_id)}"}
    if nick:
        await client.put("/v1/community/me", json={"nickname": nick}, headers=h)
    return u.user_id, h


async def _post(client, h):
    r = await client.post("/v1/community/posts", json={"category": "tips", "title": "제목", "body": "본문"}, headers=h)
    return r.json()["data"]["post_id"]


async def test_내_글에_댓글이_달리면_글쓴이에게_본인_댓글은_안_보낸다(client, db_session, sent):
    author, ha = await _user(client, db_session, "a@t.kr", "글쓴이")
    _, hb = await _user(client, db_session, "b@t.kr", "몽글이")
    pid = await _post(client, ha)
    await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "좋아요"}, headers=hb)
    await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "감사해요"}, headers=ha)   # 본인 글에 본인 댓글
    assert [(u, m["title"], m["body"], m["url"]) for u, m in sent] == \
        [(author, "새 댓글이 달렸어요 💬", "몽글이님이 내 글에 댓글을 남겼어요.", f"post.html?id={pid}")]
    assert "좋아요" not in json.dumps(sent[0][1], ensure_ascii=False)                                  # 내용은 안 넣음


async def test_답글은_원_댓글_쓴_사람에게만_글쓴이에게는_안_간다(client, db_session, sent):
    _, ha = await _user(client, db_session, "a@t.kr", "글쓴이")
    c1, hc = await _user(client, db_session, "c@t.kr", "댓글러")
    _, hr = await _user(client, db_session, "r@t.kr", "답글러")
    pid = await _post(client, ha)
    cid = (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "첫 댓글"}, headers=hc)).json()["data"]["comment_id"]
    sent.clear()                                                         # 위 댓글 알림(글쓴이)은 빼고 본다
    rid = (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "답글", "parent_id": cid},
                             headers=hr)).json()["data"]["comment_id"]
    await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "내 답글", "parent_id": cid}, headers=hc)  # 본인 댓글에 본인 답글
    assert [(u, m["title"], m["url"]) for u, m in sent] == \
        [(c1, "내 댓글에 답글이 달렸어요 💬", f"post.html?id={pid}#c-{rid}")]          # 글쓴이에게는 안 감


async def test_답글에_단_답글도_원_댓글_쓴_사람에게(client, db_session, sent):
    _, ha = await _user(client, db_session, "a@t.kr", "글쓴이")
    c1, hc = await _user(client, db_session, "c@t.kr", "댓글러")
    _, hr = await _user(client, db_session, "r@t.kr", "답글러")
    _, hs = await _user(client, db_session, "s@t.kr", "또답글")
    pid = await _post(client, ha)
    cid = (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "첫 댓글"}, headers=hc)).json()["data"]["comment_id"]
    rid = (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "답글", "parent_id": cid},
                             headers=hr)).json()["data"]["comment_id"]
    sent.clear()
    await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "답글의 답글", "parent_id": rid}, headers=hs)
    assert [u for u, _ in sent] == [c1]                                  # 답글 쓴 사람이 아니라 원 댓글 쓴 사람에게


async def test_닉네임이_없으면_누군가(db_session, sent):
    async with db_session() as s:
        u = User(email="x@t.kr", password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(PushSubscription(user_id=u.user_id, endpoint="https://push.example.com/x", p256dh="p", auth="a", created_at=NOW))
        await s.commit()
        await notify_service.reply_added(s, "post-1", "c-9", u.user_id, "someone-else")
    assert sent[0][1]["body"] == "누군가님이 내 댓글에 답글을 남겼어요." and sent[0][1]["url"] == "post.html?id=post-1#c-c-9"


async def test_문의에_답변하면_문의한_사람에게(client, db_session, sent):
    uid, _ = await _user(client, db_session, "q@t.kr")
    async with db_session() as s:
        inq = Inquiry(user_id=uid, title="질문", body="내용", created_at=NOW)
        s.add(inq)
        await s.commit()
        await inquiry_service.admin_answer(s, "admin@t.kr", inq.inquiry_id, "답변")
    assert [(u, m["title"], m["url"]) for u, m in sent] == [(uid, "문의에 답변이 도착했어요 💌", "inquiries.html")]


async def test_파티에_들어오면_이미_있던_멤버에게만(client, db_session, sent):
    a, _ = await _user(client, db_session, "a@t.kr", "파티장")
    b, _ = await _user(client, db_session, "b@t.kr", "새친구")
    async with db_session() as s:
        code = (await party_service.challenge_options(s))[0].challenge_code
        info = await party_service.create(s, a, "아침걷기", None, code)
    async with db_session() as s:
        await party_service.join(s, b, info.invite_code)
    assert [(u, m["body"], m["url"]) for u, m in sent] == [(a, "새친구님이 우리 파티에 참여했어요.", "party-home.html")]

async def test_지워져_자리만_남은_원_댓글_작성자에게는_보내지_않는다(client, db_session, sent):
    _, ha = await _user(client, db_session, "a@t.kr", "글쓴이")
    _, hc = await _user(client, db_session, "c@t.kr", "댓글러")
    _, hr = await _user(client, db_session, "r@t.kr", "답글러")
    _, hs = await _user(client, db_session, "s@t.kr", "또답글")
    pid = await _post(client, ha)
    cid = (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "첫 댓글"}, headers=hc)).json()["data"]["comment_id"]
    rid = (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "답글", "parent_id": cid},
                             headers=hr)).json()["data"]["comment_id"]
    assert (await client.delete(f"/v1/community/comments/{cid}", headers=hc)).status_code == 204   # 원 댓글 삭제 (답글이 있어 자리만 남음)
    sent.clear()
    r = await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "답글의 답글", "parent_id": rid}, headers=hs)
    assert r.status_code == 201 and sent == []                                                   # 답글은 달리지만 알림은 없음