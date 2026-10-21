"""이메일 컬럼 암호화 (이슈 #144): DB에는 잠근 이메일과 찾기용 지문만 남고, 앱은 평소처럼 이메일을 쓴다."""
from datetime import date

import pytest
from sqlalchemy import select, text

from app.core import pii
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.admin_audit import AdminAuditLog
from app.models.user import User, UserProfile
from app.services import account_service
from tests.test_signup_consent import body, seed_policies

pytestmark = pytest.mark.asyncio
ADMIN = "admin@test.kr"


async def make(Session, email: str, status: str = "active") -> tuple[str, dict]:
    async with Session() as s:
        u = User(email=email, password_hash=hash_password("password1"), status=status)
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1985, 5, 5)))
        await s.commit()
        return u.user_id, {"Authorization": f"Bearer {create_access_token(u.user_id)}"}


async def raw_row(Session, user_id: str):
    async with Session() as s:
        return (await s.execute(text("SELECT email_enc, email_hash FROM users WHERE user_id = :u"),
                                {"u": user_id})).one()


async def test_DB에는_평문_이메일이_남지_않는다(db_session):
    uid, _ = await make(db_session, "  Hong.GilDong@Test.kr ")
    enc, h = await raw_row(db_session, uid)
    async with db_session() as s:                            # 옛 평문 이메일 칸은 아예 없음 (2단계에서 삭제)
        cols = (await s.execute(text("SELECT * FROM users LIMIT 0"))).keys()
    assert "email" not in cols
    assert "hong" not in enc.lower() and enc.startswith("gAAAA")   # 잠근 값(Fernet)
    assert h == pii.email_hash("hong.gildong@test.kr")
    async with db_session() as s:
        assert (await s.get(User, uid)).email == "hong.gildong@test.kr"   # 앱에서는 정리된 이메일로 풀려 나옴


async def test_대소문자와_공백이_달라도_같은_이메일로_로그인한다(client, db_session):
    await make(db_session, "a@test.kr")
    r = await client.post("/v1/auth/login", json={"email": "  A@Test.KR ", "password": "password1"})
    assert r.status_code == 200


async def test_대소문자만_다른_이메일로는_다시_가입할_수_없다(client, db_session):
    ids = await seed_policies(db_session)
    assert (await client.post("/v1/auth/signup", json=body(ids, email="new@test.kr"))).status_code == 201
    r = await client.post("/v1/auth/signup", json=body(ids, email="NEW@Test.kr"))
    assert r.status_code == 409


async def test_탈퇴하면_같은_이메일로_다시_가입할_수_있다(client, db_session):
    ids = await seed_policies(db_session)
    assert (await client.post("/v1/auth/signup", json=body(ids, email="back@test.kr"))).status_code == 201
    async with db_session() as s:
        user = (await s.execute(select(User).where(User.email == "back@test.kr"))).scalar_one()
        await account_service.delete_account_data(s, user)          # 탈퇴: 이메일이 익명 값으로 바뀌며 지문도 바뀜
        await s.commit()
        uid = user.user_id
    enc, h = await raw_row(db_session, uid)
    assert h != pii.email_hash("back@test.kr")
    r = await client.post("/v1/auth/signup", json=body(ids, email="back@test.kr"))
    assert r.status_code == 201                                     # 같은 이메일로 재가입


async def test_내_데이터_내려받기에는_풀린_이메일만_나온다(client, db_session):
    _, h = await make(db_session, "mine@test.kr")
    r = await client.get("/v1/users/me/data-export", headers=h)
    assert r.status_code == 200
    me = r.json()["data"]["users"][0]
    assert me["email"] == "mine@test.kr"
    assert not {"email_enc", "email_hash", "password_hash"} & set(me)
    assert "gAAAA" not in r.text                                    # 잠긴 값이 그대로 나가지 않음


async def test_관리자는_필요할_때만_전체_이메일을_보고_기록이_남는다(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)
    _, admin = await make(db_session, ADMIN)
    uid, member = await make(db_session, "secret.person@test.kr")
    detail = (await client.get(f"/v1/admin/users/{uid}", headers=admin)).json()["data"]
    assert "secret.person" not in str(detail)                        # 평소에는 가린 이메일
    r = await client.get(f"/v1/admin/users/{uid}/email", headers=admin)
    assert r.status_code == 200 and r.json()["data"]["email"] == "secret.person@test.kr"
    assert (await client.get(f"/v1/admin/users/{uid}/email", headers=member)).status_code == 403
    async with db_session() as s:
        logs = (await s.execute(select(AdminAuditLog.actor_email, AdminAuditLog.action, AdminAuditLog.target)
                                .where(AdminAuditLog.action == "user_email_view"))).all()
    assert logs == [(ADMIN, "user_email_view", uid[-8:])]


async def test_탈퇴한_계정은_이메일_보기가_안_된다(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)
    _, admin = await make(db_session, ADMIN)
    uid, _ = await make(db_session, "gone@test.kr", status="deleted")
    assert (await client.get(f"/v1/admin/users/{uid}/email", headers=admin)).status_code == 404


async def test_쿼리에서_이메일은_정확히_같을_때만_찾는다(db_session):
    uid, _ = await make(db_session, "q@test.kr")
    async with db_session() as s:
        assert (await s.execute(select(User.user_id).where(User.email == " Q@test.kr"))).scalar_one() == uid
        assert (await s.execute(select(User.user_id).where(User.email.in_(["x@test.kr", "q@test.kr"])))).scalar_one() == uid
    with pytest.raises(NotImplementedError):
        User.email.ilike("%q%")                                     # 부분 검색은 조용히 틀리지 않고 바로 오류


async def test_키가_없으면_잠그지_않고_멈춘다(monkeypatch):
    monkeypatch.setattr(settings, "PII_ENC_KEY", "")
    with pytest.raises(RuntimeError):
        pii.encrypt("a@test.kr")
    monkeypatch.setattr(settings, "PII_HASH_KEY", "")
    with pytest.raises(RuntimeError):
        pii.email_hash("a@test.kr")


def test_이메일_정리와_LIKE_패턴():
    from app.services.admin_users_service import like_match
    assert pii.normalize_email("  A@B.KR ") == "a@b.kr"
    assert like_match("%@purge.kr", "t1@purge.kr") and like_match("t_@PURGE.kr", "t1@purge.kr")
    assert not like_match("%@purge.kr", "t1@purge.kr.evil") and not like_match("a.b@x.kr", "aXb@x.kr")
