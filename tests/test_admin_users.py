"""관리자 가입자 목록·상세, 일괄 삭제 테스트."""
from datetime import date

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.eligibility import EligibilityAssessment
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio

ADMIN = "admin@test.kr"


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)


async def make(Session, email: str, with_eligibility: bool = False) -> tuple[str, dict]:
    async with Session() as s:
        user = User(email=email, password_hash="x", status="active")
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        if with_eligibility:
            s.add(EligibilityAssessment(
                user_id=user.user_id, result_code="eligible", age_eligible=True, diagnosed_cad=False,
                emergency_flag=False, assessed_at=user.created_at or __import__("datetime").datetime.utcnow(),
            ))
        await s.commit()
        return user.user_id, {"Authorization": f"Bearer {create_access_token(user.user_id)}"}


async def test_일반_사용자는_관리자_조회가_막힌다(client, db_session):
    _, h = await make(db_session, "user@test.kr")
    for path in ("/v1/admin/users",):
        assert (await client.get(path, headers=h)).status_code == 403
    assert (await client.post("/v1/admin/purge", json={"patterns": ["%@a.com"]}, headers=h)).status_code == 403


async def test_가입자_목록은_이메일을_가리고_건강정보를_담지_않는다(client, db_session):
    _, h = await make(db_session, ADMIN)
    uid, _ = await make(db_session, "hong.gildong@test.kr", with_eligibility=True)
    r = await client.get("/v1/admin/users", headers=h)
    assert r.status_code == 200
    item = next(i for i in r.json()["data"]["items"] if i["user_id"] == uid)
    assert item["email_masked"] == "ho**********@test.kr"
    assert item["stage"] == "eligibility" and item["health_consent"] == "none"
    assert not ({"sbp", "dbp", "weight", "height", "diary"} & set(item))
    assert "hong.gildong" not in r.text


async def test_목록_검색과_단계_필터(client, db_session):
    _, h = await make(db_session, ADMIN)
    await make(db_session, "a1@test.kr")
    await make(db_session, "b2@test.kr", with_eligibility=True)
    # 이메일은 암호화되어 있어 전체 이메일(대소문자·앞뒤 공백 무관)로만 찾는다. 일부 글자로는 찾지 않는다
    r = await client.get("/v1/admin/users", params={"q": " B2@Test.kr "}, headers=h)
    assert [i["email_masked"] for i in r.json()["data"]["items"]] == ["b*@test.kr"]
    r = await client.get("/v1/admin/users", params={"q": "b2"}, headers=h)
    assert r.json()["data"]["items"] == []
    r = await client.get("/v1/admin/users", params={"stage": "signup"}, headers=h)
    emails = {i["email_masked"] for i in r.json()["data"]["items"]}
    assert "a*@test.kr" in emails and "b*@test.kr" not in emails


async def test_가입자_상세와_없는_번호(client, db_session):
    _, h = await make(db_session, ADMIN)
    uid, _ = await make(db_session, "c3@test.kr", with_eligibility=True)
    r = await client.get(f"/v1/admin/users/{uid}", headers=h)
    d = r.json()["data"]
    assert d["stages_done"] == ["signup", "eligibility"] and d["cycles"] == 0 and d["consents"] == []
    assert (await client.get("/v1/admin/users/nope", headers=h)).status_code == 404


async def test_일괄_삭제_미리보기와_실제_삭제(client, db_session):
    _, h = await make(db_session, ADMIN)
    await make(db_session, "t1@purge.kr")
    await make(db_session, "t2@purge.kr")
    prev = await client.post("/v1/admin/purge", json={"patterns": ["%@purge.kr"]}, headers=h)
    assert prev.json()["data"]["count"] == 2 and prev.json()["data"]["applied"] is False
    # 인원수가 다르면 실행되지 않는다
    bad = await client.post("/v1/admin/purge", json={"patterns": ["%@purge.kr"], "apply": True, "confirm_count": 1}, headers=h)
    assert bad.status_code == 409
    ok = await client.post("/v1/admin/purge", json={"patterns": ["%@purge.kr"], "apply": True, "confirm_count": 2}, headers=h)
    assert ok.json()["data"]["done"] == 2 and ok.json()["data"]["failed"] == 0
    async with db_session() as s:
        everyone = (await s.execute(select(User))).scalars().all()
        assert [u for u in everyone if u.email.endswith("@purge.kr")] == []   # 이메일이 익명 값으로 바뀌었다
        assert (await s.execute(select(User).where(User.status == "deleted"))).scalars().all()


async def test_너무_넓은_패턴과_관리자_보호(client, db_session):
    _, h = await make(db_session, ADMIN)
    assert (await client.post("/v1/admin/purge", json={"patterns": ["%"]}, headers=h)).status_code == 422
    r = await client.post("/v1/admin/purge", json={"patterns": ["admin@%"]}, headers=h)
    assert r.json()["data"]["count"] == 0   # 관리자 계정은 대상에서 빠진다


async def test_관리자_API는_3초_안에_응답한다(client, db_session):
    """NFR-ADM-001: 가입자가 많아도(300명) 목록·상세·삭제 미리보기가 3초 이내."""
    import time
    _, h = await make(db_session, ADMIN)
    async with db_session() as s:
        s.add_all([User(email=f"bulk{i}@perf.kr", password_hash="x", status="active") for i in range(300)])
        await s.commit()
    uid = (await client.get("/v1/admin/users", params={"limit": 1}, headers=h)).json()["data"]["items"][0]["user_id"]
    calls = [
        client.get("/v1/admin/users", params={"limit": 50, "stage": "signup"}, headers=h),
        client.get(f"/v1/admin/users/{uid}", headers=h),
        client.post("/v1/admin/purge", json={"patterns": ["%@perf.kr"]}, headers=h),
    ]
    for call in calls:
        start = time.perf_counter()
        r = await call
        assert r.status_code == 200 and time.perf_counter() - start < 3


async def test_가입자_조회와_삭제가_행위_기록에_남는다(client, db_session):
    _, h = await make(db_session, ADMIN)
    await make(db_session, "log1@audit.kr")
    await client.get("/v1/admin/users", headers=h)
    prev = await client.post("/v1/admin/purge", json={"patterns": ["%@audit.kr"]}, headers=h)
    await client.post("/v1/admin/purge", json={"patterns": ["%@audit.kr"], "apply": True, "confirm_count": prev.json()["data"]["count"]}, headers=h)
    logs = (await client.get("/v1/admin/audit-logs", headers=h)).json()["data"]
    actions = {row["action"] for row in logs}
    assert {"users_view", "purge_preview", "purge_apply"} <= actions
    assert all(row["actor_email"] == ADMIN for row in logs)
    assert "audit.kr" not in str(logs)      # 기록에는 사용자 이메일이 들어가지 않는다
