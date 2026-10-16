"""새 1:1 문의·비회원 문의가 접수되면 관리자에게 디스코드 알림을 보낸다. 제목·내용은 보내지 않는다."""
from datetime import date

import pytest

from app.core.security import create_access_token
from app.models.user import User, UserProfile
from app.services import admin_alert

pytestmark = pytest.mark.asyncio
TITLE, BODY = "아주 특이한 문의 제목", "아주 특이한 문의 내용"


@pytest.fixture
def sent(monkeypatch):
    """보낸 알림 문구를 모은다 (실제로 디스코드에 보내지 않음)."""
    box: list[str] = []
    monkeypatch.setattr(admin_alert, "notify", box.append)
    return box


async def member(Session) -> dict:
    async with Session() as s:
        u = User(email="q@test.kr", password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        return {"Authorization": f"Bearer {create_access_token(u.user_id)}"}


async def test_새_1대1_문의가_들어오면_알린다(client, db_session, sent):
    h = await member(db_session)
    r = await client.post("/v1/inquiries", json={"title": TITLE, "body": BODY}, headers=h)
    assert r.status_code == 201
    assert len(sent) == 1 and "1:1 문의" in sent[0]
    assert TITLE not in sent[0] and BODY not in sent[0]


async def test_막힌_1대1_문의는_알리지_않는다(client, db_session, sent):
    h = await member(db_session)
    for i in range(5):                                                  # 답을 기다리는 문의는 5개까지
        assert (await client.post("/v1/inquiries", json={"title": f"문의 {i}", "body": "내용"}, headers=h)).status_code == 201
    r = await client.post("/v1/inquiries", json={"title": "여섯째", "body": "내용"}, headers=h)
    assert r.status_code == 429
    assert len(sent) == 5                                               # 막힌 여섯째는 알리지 않음


async def test_새_비회원_문의가_들어오면_알린다(client, sent):
    r = await client.post("/v1/guest-inquiries", json={"title": TITLE, "body": BODY})
    assert r.status_code == 201
    assert len(sent) == 1 and "비회원 문의" in sent[0]
    assert TITLE not in sent[0] and BODY not in sent[0]


async def test_봇이_보낸_비회원_문의는_알리지_않는다(client, sent):
    r = await client.post("/v1/guest-inquiries", json={"title": "광고", "body": "광고", "website": "http://spam.example"})
    assert r.status_code == 201                                         # 봇에게는 성공처럼 보이지만
    assert sent == []                                                   # 저장도 알림도 하지 않는다


async def test_횟수_초과로_막힌_비회원_문의는_알리지_않는다(client, sent):
    codes = [(await client.post("/v1/guest-inquiries", json={"title": f"문의 {i}", "body": "내용"})).status_code
             for i in range(4)]
    assert codes == [201, 201, 201, 429]                                # 같은 IP는 한 시간에 3번까지
    assert len(sent) == 3
