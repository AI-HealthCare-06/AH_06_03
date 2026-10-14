"""비회원 문의: 로그인 없이 문의하고 조회 번호로 답변을 보며, 스팸을 막는다."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, utcnow
from app.models.guest_inquiry import GuestInquiry
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio

ADMIN = "admin@test.kr"
BODY = {"title": "로그인이 안 돼요", "body": "비밀번호를 틀렸다고 나와요", "website": ""}


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)


async def make_admin(Session, email=ADMIN) -> dict:
    async with Session() as s:
        user = User(email=email, password_hash="x", status="active")
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        return {"Authorization": f"Bearer {create_access_token(user.user_id)}"}


def ip(n: str) -> dict:
    return {"X-Forwarded-For": n}


async def test_문의_조회번호_답변_흐름(client, db_session):
    admin = await make_admin(db_session)
    r = await client.post("/v1/guest-inquiries", json=BODY, headers=ip("1.1.1.1"))
    assert r.status_code == 201
    code = r.json()["data"]["code"]
    assert len(code) == 14 and code.count("-") == 2
    v = (await client.get(f"/v1/guest-inquiries/{code}")).json()["data"]        # 로그인 없이 조회
    assert v["title"] == BODY["title"] and v["answer"] is None
    assert (await client.get(f"/v1/guest-inquiries/{code.lower().replace('-', '')}")).status_code == 200   # 대소문자·하이픈 무시
    # 관리자: 목록 → 답변
    lst = (await client.get("/v1/admin/guest-inquiries", params={"status": "open"}, headers=admin)).json()["data"]
    assert lst["total"] == 1
    iid = lst["items"][0]["inquiry_id"]
    assert (await client.put(f"/v1/admin/guest-inquiries/{iid}/answer", json={"answer": "비밀번호를 다시 확인해 보세요."}, headers=admin)).status_code == 200
    assert (await client.get(f"/v1/guest-inquiries/{code}")).json()["data"]["answer"] == "비밀번호를 다시 확인해 보세요."


async def test_번호와_IP는_해시로만_저장된다(client, db_session):
    code = (await client.post("/v1/guest-inquiries", json=BODY, headers=ip("9.9.9.9"))).json()["data"]["code"]
    async with db_session() as s:
        row = (await s.execute(select(GuestInquiry))).scalar_one()
    raw = code.replace("-", "")
    assert raw not in row.code_hash and "9.9.9.9" not in row.ip_hash and len(row.code_hash) == 64


async def test_틀린_번호와_일반_사용자(client, db_session):
    assert (await client.get("/v1/guest-inquiries/AAAA-BBBB-CCCC")).status_code == 404
    assert (await client.get("/v1/admin/guest-inquiries")).status_code == 401


async def test_숨은_칸이_채워진_봇은_저장하지_않는다(client, db_session):
    r = await client.post("/v1/guest-inquiries", json={**BODY, "website": "http://spam"}, headers=ip("2.2.2.2"))
    assert r.status_code == 201 and r.json()["data"]["code"]        # 봇에게는 성공한 것처럼 보인다
    async with db_session() as s:
        assert (await s.execute(select(GuestInquiry))).scalars().all() == []


async def test_같은_IP는_1시간에_3개까지(client, db_session):
    for n in range(3):
        assert (await client.post("/v1/guest-inquiries", json={**BODY, "title": f"t{n}"}, headers=ip("3.3.3.3"))).status_code == 201
    r = await client.post("/v1/guest-inquiries", json=BODY, headers=ip("3.3.3.3"))
    assert r.status_code == 429 and r.json()["error"]["code"] == "GUEST_INQUIRY_RATE_LIMIT"
    assert (await client.post("/v1/guest-inquiries", json=BODY, headers=ip("4.4.4.4"))).status_code == 201    # 다른 IP는 괜찮다


async def test_링크가_많은_문의는_거절한다(client, db_session):
    spam = {**BODY, "body": "http://a.com http://b.com http://c.com"}
    assert (await client.post("/v1/guest-inquiries", json=spam, headers=ip("5.5.5.5"))).status_code == 422


async def test_30일이_지난_문의는_새_문의가_들어올_때_지워진다(client, db_session):
    async with db_session() as s:
        s.add(GuestInquiry(code_hash="a" * 64, ip_hash="b" * 64, title="old", body="x", created_at=utcnow() - timedelta(days=31)))
        s.add(GuestInquiry(code_hash="c" * 64, ip_hash="d" * 64, title="recent", body="x", created_at=utcnow() - timedelta(days=10)))
        await s.commit()
    assert (await client.post("/v1/guest-inquiries", json=BODY, headers=ip("6.6.6.6"))).status_code == 201
    async with db_session() as s:
        titles = sorted(t for (t,) in (await s.execute(select(GuestInquiry.title))).all())
    assert titles == sorted([BODY["title"], "recent"])
