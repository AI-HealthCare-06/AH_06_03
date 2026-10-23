"""웹 푸시: 구독 등록·해제, 종류별 설정, 발송(설정 꺼짐·만료 구독 삭제)."""
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.push import PushSubscription
from app.models.user import User, UserProfile
from app.services import push_service

pytestmark = pytest.mark.asyncio

SUB = {"endpoint": "https://push.example.com/abc", "keys": {"p256dh": "p-key", "auth": "a-key"}}


class GoneError(Exception):
    """만료된 구독처럼 410을 돌려주는 가짜 오류."""
    def __init__(self, status):
        super().__init__(status)
        self.response = SimpleNamespace(status_code=status)


async def _user(Session, email):
    async with Session() as s:
        u = User(email=email, password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1990, 1, 1)))
        await s.commit()
        return u.user_id, {"Authorization": f"Bearer {create_access_token(u.user_id)}"}


async def _subs(Session):
    async with Session() as s:
        return (await s.execute(select(PushSubscription))).scalars().all()


async def test_같은_기기를_다시_등록하면_한_줄로_갱신되고_다른_사람이면_넘어간다(client, db_session):
    a, ha = await _user(db_session, "a@t.kr")
    b, hb = await _user(db_session, "b@t.kr")
    assert (await client.put("/v1/push/subscription", json=SUB, headers=ha)).status_code == 200
    await client.put("/v1/push/subscription", json={**SUB, "keys": {"p256dh": "new", "auth": "new"}}, headers=ha)
    subs = await _subs(db_session)
    assert len(subs) == 1 and subs[0].p256dh == "new"
    await client.put("/v1/push/subscription", json=SUB, headers=hb)          # 같은 기기로 다른 사람이 로그인
    assert [s.user_id for s in await _subs(db_session)] == [b]


async def test_내_구독만_해제할_수_있다(client, db_session):
    _, ha = await _user(db_session, "a@t.kr")
    _, hb = await _user(db_session, "b@t.kr")
    await client.put("/v1/push/subscription", json=SUB, headers=ha)
    await client.request("DELETE", "/v1/push/subscription", json={"endpoint": SUB["endpoint"]}, headers=hb)
    assert len(await _subs(db_session)) == 1                                    # 남의 것은 그대로
    r = await client.request("DELETE", "/v1/push/subscription", json={"endpoint": SUB["endpoint"]}, headers=ha)
    assert r.status_code == 204 and await _subs(db_session) == []


async def test_설정은_기본_모두_켜짐이고_보낸_것만_바뀐다(client, db_session):
    _, h = await _user(db_session, "a@t.kr")
    assert (await client.get("/v1/push/settings", headers=h)).json()["data"] == \
        {"comment": True, "inquiry": True, "party": True, "challenge": True, "breakfast": True}
    d = (await client.patch("/v1/push/settings", json={"challenge": False}, headers=h)).json()["data"]
    assert d == {"comment": True, "inquiry": True, "party": True, "challenge": False, "breakfast": True}


async def test_발송_설정_꺼짐이면_안_보내고_만료_구독은_지운다(client, db_session, monkeypatch):
    uid, h = await _user(db_session, "a@t.kr")
    await client.put("/v1/push/subscription", json=SUB, headers=h)
    await client.put("/v1/push/subscription", json={**SUB, "endpoint": "https://push.example.com/old"}, headers=h)
    monkeypatch.setattr(settings, "VAPID_PRIVATE_KEY", "test-key")
    sent_to = []

    def fake(sub, payload):
        if sub.endpoint.endswith("/old"):
            raise GoneError(410)
        sent_to.append((sub.endpoint, payload))

    monkeypatch.setattr(push_service, "_webpush", fake)
    async with db_session() as s:
        r = await push_service.send(s, uid, "comment", "새 댓글이 달렸어요 💬", "누군가님이 내 글에 댓글을 남겼어요.", "post.html?id=1")
    assert (r.sent, r.gone, r.failed) == (1, 1, 0) and '"url": "post.html?id=1"' in sent_to[0][1]
    assert [s.endpoint for s in await _subs(db_session)] == [SUB["endpoint"]]   # 410 받은 기기는 지워짐
    await client.patch("/v1/push/settings", json={"comment": False}, headers=h)
    async with db_session() as s:
        assert (await push_service.send(s, uid, "comment", "t", "b", "u")).sent == 0    # 꺼 두면 안 보냄


async def test_VAPID_키가_없으면_보내지_않는다(db_session):
    uid, _ = await _user(db_session, "a@t.kr")
    async with db_session() as s:
        assert (await push_service.send(s, uid, "comment", "t", "b", "u")).sent == 0


async def test_내_데이터_내려받기에_기기_암호화_키는_안_나간다(client, db_session):
    _, h = await _user(db_session, "a@t.kr")
    await client.put("/v1/push/subscription", json=SUB, headers=h)
    r = await client.get("/v1/users/me/data-export", headers=h)
    assert r.status_code == 200
    assert "p-key" not in r.text and "a-key" not in r.text            # p256dh·auth 값이 없어야 함