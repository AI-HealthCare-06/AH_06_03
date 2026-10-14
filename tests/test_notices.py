"""서비스 안 공지 테스트: 이용자 목록(로그인 없이, 게시 중만), 관리자 작성·수정·내리기, 입력 검사, 권한, 관리자 행위 기록."""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, utcnow
from app.models.admin_audit import AdminAuditLog
from app.models.notice import Notice
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@test.kr")


async def make_account(Session, email: str) -> dict:
    async with Session() as s:
        user = User(email=email, password_hash="x", status="active")
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        return {"Authorization": f"Bearer {create_access_token(user.user_id)}"}


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds") + "Z"


async def post(client, h, **body):
    body.setdefault("title", "점검 안내")
    body.setdefault("body", "내일 새벽에 잠깐 점검해요.")
    return await client.post("/v1/admin/notices", json=body, headers=h)


async def public_titles(client) -> list[str]:
    r = await client.get("/v1/notices")                      # 로그인 없이
    assert r.status_code == 200, r.text
    return [n["title"] for n in r.json()["data"]]


async def test_public_list_needs_no_login_and_shows_only_active(client, db_session):
    h = await make_account(db_session, "admin@test.kr")
    now = utcnow()
    await post(client, h, title="지금 게시")
    await post(client, h, title="예정", starts_at=iso(now + timedelta(hours=2)))
    await post(client, h, title="이미 끝남", starts_at=iso(now - timedelta(days=2)), ends_at=iso(now - timedelta(days=1)))
    await post(client, h, title="곧 끝남", starts_at=iso(now - timedelta(hours=1)), ends_at=iso(now + timedelta(hours=1)))
    titles = await public_titles(client)
    assert sorted(titles) == ["곧 끝남", "지금 게시"]
    raw = (await client.get("/v1/notices")).json()["data"][0]
    assert set(raw) == {"notice_id", "title", "body", "starts_at", "ends_at"}        # 쓴 관리자 이메일 등은 안 나감


async def test_public_list_is_newest_first_and_limited(client, db_session):
    h = await make_account(db_session, "admin@test.kr")
    now = utcnow()
    for i in range(12):
        await post(client, h, title=f"공지{i:02d}", starts_at=iso(now - timedelta(hours=12 - i)))
    titles = await public_titles(client)
    assert len(titles) == 10 and titles[0] == "공지11" and titles[-1] == "공지02"


async def test_admin_endpoints_need_admin(client, db_session):
    user = await make_account(db_session, "user@test.kr")
    assert (await client.post("/v1/admin/notices", json={"title": "a", "body": "b"})).status_code == 401
    for method, path, body in (("get", "/v1/admin/notices", None), ("post", "/v1/admin/notices", {"title": "a", "body": "b"}),
                               ("patch", "/v1/admin/notices/x", {"end_now": True})):
        r = await getattr(client, method)(path, headers=user, **({"json": body} if body else {}))
        assert r.status_code == 403 and r.json()["error"]["code"] == "ADMIN_FORBIDDEN"
    assert await public_titles(client) == []


async def test_create_defaults_and_admin_list_status(client, db_session):
    h = await make_account(db_session, "admin@test.kr")
    now = utcnow()
    r = await post(client, h, title="  공백 정리  ")
    assert r.status_code == 201
    created = r.json()["data"]
    assert created["title"] == "공백 정리" and created["status"] == "active" and created["created_by"] == "admin@test.kr"
    assert created["ends_at"] is None and abs((datetime.fromisoformat(created["starts_at"]) - now).total_seconds()) < 5
    await post(client, h, title="예정", starts_at=iso(now + timedelta(days=1)))
    await post(client, h, title="끝남", starts_at=iso(now - timedelta(days=2)), ends_at=iso(now - timedelta(days=1)))
    listing = (await client.get("/v1/admin/notices", headers=h)).json()["data"]
    assert {n["title"]: n["status"] for n in listing} == {"공백 정리": "active", "예정": "upcoming", "끝남": "ended"}
    assert len((await client.get("/v1/admin/notices?limit=1", headers=h)).json()["data"]) == 1


async def test_input_is_validated(client, db_session):
    h = await make_account(db_session, "admin@test.kr")
    now = utcnow()
    bad = [
        {"title": "", "body": "b"}, {"title": "a" * 101, "body": "b"}, {"title": "a", "body": ""}, {"title": "a", "body": "b" * 2001},
        {"title": "a", "body": "b", "extra": 1},
        {"title": "a", "body": "b", "starts_at": iso(now), "ends_at": iso(now)},                       # 끝이 시작보다 뒤가 아님
        {"title": "a", "body": "b", "starts_at": iso(now), "ends_at": iso(now - timedelta(hours=1))},
        {"title": "a", "body": "b", "ends_at": iso(now - timedelta(hours=1))},                          # 시작 기본값(지금)보다 앞
    ]
    for body in bad:
        r = await client.post("/v1/admin/notices", json=body, headers=h)
        assert r.status_code == 422, body
    assert await public_titles(client) == []


async def test_update_and_take_down(client, db_session):
    h = await make_account(db_session, "admin@test.kr")
    nid = (await post(client, h, title="처음 제목")).json()["data"]["notice_id"]
    r = await client.patch(f"/v1/admin/notices/{nid}", json={"title": "고친 제목", "body": "고친 내용"}, headers=h)
    assert r.status_code == 200 and r.json()["data"]["title"] == "고친 제목" and r.json()["data"]["updated_at"]
    assert await public_titles(client) == ["고친 제목"]
    r = await client.patch(f"/v1/admin/notices/{nid}", json={"end_now": True}, headers=h)
    assert r.status_code == 200 and r.json()["data"]["status"] == "ended"
    assert await public_titles(client) == []                                                        # 내리면 바로 안 보임


async def test_update_validation_and_not_found(client, db_session):
    h = await make_account(db_session, "admin@test.kr")
    nid = (await post(client, h)).json()["data"]["notice_id"]
    now = utcnow()
    assert (await client.patch(f"/v1/admin/notices/{nid}", json={}, headers=h)).status_code == 422
    assert (await client.patch(f"/v1/admin/notices/{nid}", json={"end_now": True, "ends_at": iso(now)}, headers=h)).status_code == 422
    assert (await client.patch(f"/v1/admin/notices/{nid}", json={"ends_at": iso(now - timedelta(days=1))}, headers=h)).status_code == 422
    assert await public_titles(client) == ["점검 안내"]                                             # 거절된 변경은 반영 안 됨
    assert (await client.patch("/v1/admin/notices/nope", json={"end_now": True}, headers=h)).status_code == 404


async def test_writes_are_recorded_without_the_body(client, db_session):
    h = await make_account(db_session, "admin@test.kr")
    nid = (await post(client, h, title="약관 변경", body="비밀 아님: 본문 전체")).json()["data"]["notice_id"]
    await client.patch(f"/v1/admin/notices/{nid}", json={"title": "약관 변경 안내"}, headers=h)
    await client.patch(f"/v1/admin/notices/{nid}", json={"title": "약관 변경 안내"}, headers=h)    # 같은 값이라 기록 없음
    async with db_session() as s:
        rows = [(a.action, a.target, a.detail) for a in (await s.execute(select(AdminAuditLog).order_by(AdminAuditLog.created_at))).scalars()
                if a.action.startswith("notice_")]
    assert rows == [("notice_create", nid[-8:], "제목: 약관 변경"), ("notice_update", nid[-8:], "바꾼 것: 제목")]
    assert all("본문 전체" not in (d or "") for _, _, d in rows)                                    # 내용은 기록에 안 남김


async def test_timezone_inputs_are_stored_as_utc(client, db_session):
    h = await make_account(db_session, "admin@test.kr")
    r = await post(client, h, starts_at="2030-01-02T09:00:00+09:00")                                # 한국 시각으로 보내도
    assert r.json()["data"]["starts_at"].startswith("2030-01-02T00:00:00")                          # UTC로 저장
    async with db_session() as s:
        assert (await s.execute(select(Notice.starts_at))).scalar_one() == datetime(2030, 1, 2, 0, 0)
