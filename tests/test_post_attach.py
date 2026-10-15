"""글에 챌린지 붙이기: 오늘 인증한 미션·공통 챌린지만, 서버가 확인한 이름과 일수만 저장한다."""
from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.core.security import create_access_token, utcnow
from app.models.challenge import Challenge, ChallengeCycle, ChallengeLog, CycleChallenge
from app.models.common_challenge import CommonChallengeCert
from app.models.user import User, UserProfile
from app.services.challenge_service import today_kst

pytestmark = pytest.mark.asyncio

ADMIN = "admin@test.kr"
POST = {"category": "challenge", "title": "오늘 인증", "body": "해냈어요"}


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)


async def make(client, Session, email, nick):
    async with Session() as s:
        u = User(email=email, password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        uid, h = u.user_id, {"Authorization": f"Bearer {create_access_token(u.user_id)}"}
    await client.put("/v1/community/me", json={"nickname": nick}, headers=h)
    return uid, h


async def start_cycle(Session, uid, today_done: bool, past_days: int):
    """4주 챌린지: 선택 미션 하나(첫 번째 시드 미션)에 오늘 포함 완료 기록을 직접 넣는다."""
    from sqlalchemy import select
    async with Session() as s:
        ch = (await s.execute(select(Challenge).order_by(Challenge.challenge_code))).scalars().first()
        today = today_kst()
        cycle = ChallengeCycle(user_id=uid, cycle_number=1, started_on=today - timedelta(days=20),
                               ended_on=today + timedelta(days=7), status="active",
                               created_at=utcnow(), updated_at=utcnow())
        s.add(cycle)
        await s.flush()
        cc = CycleChallenge(cycle_id=cycle.cycle_id, challenge_id=ch.challenge_id, selection_type="selected",
                            difficulty="medium", weekly_target=3)
        s.add(cc)
        await s.flush()
        days = [today - timedelta(days=n) for n in range(1, past_days + 1)] + ([today] if today_done else [])
        for d in days:
            s.add(ChallengeLog(cycle_challenge_id=cc.cycle_challenge_id, log_date=d, status="completed",
                               recorded_at=utcnow(), updated_at=utcnow()))
        await s.commit()
        return ch.challenge_code, ch.challenge_name


async def test_오늘_인증한_미션을_붙이면_이름과_일수가_글에_저장된다(client, db_session):
    uid, h = await make(client, db_session, "a@test.kr", "글쓴이")
    code, name = await start_cycle(db_session, uid, today_done=True, past_days=11)
    opts = (await client.get("/v1/community/attachable", headers=h)).json()["data"]
    assert opts == [{"mission_code": code, "common_challenge_id": None, "kind": "selected", "label": name, "days": 12}]
    r = await client.post("/v1/community/posts", json={**POST, "attach": {"mission_code": code}}, headers=h)
    assert r.status_code == 201
    pid = r.json()["data"]["post_id"]
    assert r.json()["data"]["attach"] == {"kind": "selected", "label": name, "days": 12}
    lst = (await client.get("/v1/community/posts", headers=h)).json()["data"]["items"][0]
    assert lst["attach"] == {"kind": "selected", "label": name, "days": 12}
    assert (await client.get(f"/v1/community/posts/{pid}", headers=h)).json()["data"]["attach"]["days"] == 12


async def test_오늘_인증하지_않았거나_내_챌린지가_아니면_붙일_수_없다(client, db_session):
    uid, h = await make(client, db_session, "a@test.kr", "글쓴이")
    _, other = await make(client, db_session, "b@test.kr", "다른사람")
    code, _ = await start_cycle(db_session, uid, today_done=False, past_days=5)      # 오늘은 안 함
    assert (await client.get("/v1/community/attachable", headers=h)).json()["data"] == []
    r = await client.post("/v1/community/posts", json={**POST, "attach": {"mission_code": code}}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ATTACH_NOT_ALLOWED"
    r = await client.post("/v1/community/posts", json={**POST, "attach": {"mission_code": code}}, headers=other)   # 남의 미션
    assert r.status_code == 409
    r = await client.post("/v1/community/posts", json={**POST, "attach": {"mission_code": "NOPE-1"}}, headers=h)
    assert r.status_code == 409
    # 둘 다 보내거나 둘 다 비면 입력 오류
    both = {"mission_code": code, "common_challenge_id": "x"}
    assert (await client.post("/v1/community/posts", json={**POST, "attach": both}, headers=h)).status_code == 422
    assert (await client.post("/v1/community/posts", json={**POST, "attach": {}}, headers=h)).status_code == 422
    # 붙이지 않은 글은 그대로 올라간다
    ok = await client.post("/v1/community/posts", json=POST, headers=h)
    assert ok.status_code == 201 and ok.json()["data"]["attach"] is None


async def test_공통_챌린지도_오늘_인증했으면_붙일_수_있다(client, db_session):
    _, admin = await make(client, db_session, ADMIN, "운영팀")
    uid, h = await make(client, db_session, "a@test.kr", "글쓴이")
    today = today_kst()
    cid = (await client.post("/v1/admin/common-challenges", headers=admin, json={
        "title": "하루 7천 걸음", "proof_type": "steps", "target_steps": 7000,
        "starts_on": str(today - timedelta(days=3)), "ends_on": str(today + timedelta(days=6))})).json()["data"]["challenge_id"]
    await client.post(f"/v1/common-challenges/{cid}/join", headers=h)
    async with db_session() as s:
        for n in range(1, 4):
            s.add(CommonChallengeCert(challenge_id=cid, user_id=uid, cert_date=today - timedelta(days=n), steps=8000, created_at=utcnow()))
        await s.commit()
    r = await client.post("/v1/community/posts", json={**POST, "attach": {"common_challenge_id": cid}}, headers=h)
    assert r.status_code == 409                                                   # 오늘은 아직 인증 전
    await client.post(f"/v1/common-challenges/{cid}/certify", json={"steps": 9000}, headers=h)
    opts = (await client.get("/v1/community/attachable", headers=h)).json()["data"]
    assert opts == [{"mission_code": None, "common_challenge_id": cid, "kind": "common", "label": "하루 7천 걸음", "days": 4}]
    r = await client.post("/v1/community/posts", json={**POST, "attach": {"common_challenge_id": cid}}, headers=h)
    assert r.status_code == 201
    assert r.json()["data"]["attach"] == {"kind": "common", "label": "하루 7천 걸음", "days": 4}
    assert "steps" not in str(r.json())                                           # 걸음 수는 글에 나오지 않는다


async def test_숨긴_글에서는_붙인_카드도_보이지_않는다(client, db_session):
    _, admin = await make(client, db_session, ADMIN, "운영팀")
    uid, h = await make(client, db_session, "a@test.kr", "글쓴이")
    _, rep = await make(client, db_session, "r@test.kr", "신고자")
    code, _ = await start_cycle(db_session, uid, today_done=True, past_days=2)
    pid = (await client.post("/v1/community/posts", json={**POST, "attach": {"mission_code": code}}, headers=h)).json()["data"]["post_id"]
    await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "other"}, headers=rep)
    await client.post(f"/v1/admin/reports/post/{pid}/action", json={"action": "hide"}, headers=admin)
    mine = (await client.get("/v1/community/posts", headers=h)).json()["data"]["items"][0]
    assert mine["hidden"] is True and mine["attach"] is None
