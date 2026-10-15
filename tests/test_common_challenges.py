"""공통 챌린지: 관리자가 열고, 이용자가 참여·인증하고, 인증 일수로 순위를 매기고, 끝난 뒤 순위를 확정하면 파이가 적립된다."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, utcnow
from app.models.admin_audit import AdminAuditLog
from app.models.common_challenge import CommonChallengeCert, CommonChallengeParticipant
from app.models.pie import PieLedger
from app.models.user import User, UserProfile
from app.services import account_service
from app.services.challenge_service import today_kst

pytestmark = pytest.mark.asyncio

ADMIN = "admin@test.kr"


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", ADMIN)


async def make(client, Session, email: str, nick: str | None = None) -> tuple[str, dict]:
    async with Session() as s:
        user = User(email=email, password_hash="x", status="active")
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        uid, h = user.user_id, {"Authorization": f"Bearer {create_access_token(user.user_id)}"}
    if nick:
        await client.put("/v1/community/me", json={"nickname": nick}, headers=h)
    return uid, h


async def open_challenge(client, admin, *, start: int = 0, end: int = 9, **kw) -> dict:
    today = today_kst()
    body = {"title": "하루 7천 걸음", "proof_type": "steps", "target_steps": 7000,
            "starts_on": str(today + timedelta(days=start)), "ends_on": str(today + timedelta(days=end))}
    body.update(kw)
    r = await client.post("/v1/admin/common-challenges", json=body, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()["data"]


async def test_관리자가_만들면_완주_기준은_기간의_70퍼센트가_기본이다(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    c = await open_challenge(client, admin, start=0, end=9)       # 10일
    assert c["complete_min_days"] == 7 and c["state"] == "active" and c["participants"] == 0
    assert c["rewards"] == {"first": 300, "second": 200, "third": 100, "complete": 20}
    c2 = await open_challenge(client, admin, start=0, end=29, complete_min_days=20, reward_first=500)   # 30일
    assert c2["complete_min_days"] == 20 and c2["rewards"]["first"] == 500
    listed = (await client.get("/v1/admin/common-challenges", headers=admin)).json()["data"]["items"]
    assert len(listed) == 2


async def test_챌린지_만들기_입력_검사(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    today = today_kst()
    base = {"title": "챌린지", "proof_type": "steps", "target_steps": 7000, "starts_on": str(today), "ends_on": str(today)}
    for bad in ({**base, "ends_on": str(today - timedelta(days=1))},            # 끝이 시작보다 빠름
                {**base, "target_steps": None},                                 # 걸음 수 챌린지에 목표 없음
                {**base, "proof_type": "self"},                                 # 직접 인증인데 목표 걸음 수
                {**base, "complete_min_days": 2},                               # 완주 기준이 기간보다 김 (1일 챌린지)
                {**base, "reward_first": -1}):
        assert (await client.post("/v1/admin/common-challenges", json=bad, headers=admin)).status_code == 422
    _, user = await make(client, db_session, "u@test.kr")
    assert (await client.post("/v1/admin/common-challenges", json=base, headers=user)).status_code == 403
    assert (await client.get("/v1/admin/common-challenges", headers=user)).status_code == 403


async def test_참여와_인증_규칙(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    _, no_nick = await make(client, db_session, "n@test.kr")
    _, u = await make(client, db_session, "u@test.kr", "걷는고양이")
    cid = (await open_challenge(client, admin))["challenge_id"]
    r = await client.post(f"/v1/common-challenges/{cid}/join", headers=no_nick)
    assert r.status_code == 409 and r.json()["error"]["code"] == "NICKNAME_REQUIRED"
    # 참여 전에는 인증할 수 없다
    r = await client.post(f"/v1/common-challenges/{cid}/certify", json={"steps": 8000}, headers=u)
    assert r.status_code == 409 and r.json()["error"]["code"] == "NOT_JOINED"
    assert (await client.post(f"/v1/common-challenges/{cid}/join", headers=u)).json()["data"] == {"joined": True, "participants": 1}
    assert (await client.post(f"/v1/common-challenges/{cid}/join", headers=u)).json()["error"]["code"] == "ALREADY_JOINED"
    # 걸음 수 인증: 숫자가 없거나 목표에 못 미치면 안 된다
    assert (await client.post(f"/v1/common-challenges/{cid}/certify", headers=u)).json()["error"]["code"] == "STEPS_REQUIRED"
    r = await client.post(f"/v1/common-challenges/{cid}/certify", json={"steps": 6999}, headers=u)
    assert r.status_code == 422 and r.json()["error"]["code"] == "STEPS_NOT_ENOUGH"
    ok = await client.post(f"/v1/common-challenges/{cid}/certify", json={"steps": 7000}, headers=u)
    assert ok.status_code == 201 and ok.json()["data"] == {"my_days": 1, "my_rank": 1}
    # 같은 날 두 번은 안 된다
    r = await client.post(f"/v1/common-challenges/{cid}/certify", json={"steps": 9000}, headers=u)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ALREADY_CERTIFIED"
    d = (await client.get(f"/v1/common-challenges/{cid}", headers=u)).json()["data"]
    assert d["certified_today"] is True and d["my_days"] == 1 and d["joined"] is True and d["participants"] == 1
    assert d["total_days"] == 10 and "steps" not in str(d["top"])         # 순위에는 걸음 수를 내보내지 않는다


async def test_직접_인증_챌린지는_걸음_수_없이_인증한다(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    _, u = await make(client, db_session, "u@test.kr", "초록접시")
    cid = (await open_challenge(client, admin, proof_type="self", target_steps=None, title="식후 10분 걷기"))["challenge_id"]
    await client.post(f"/v1/common-challenges/{cid}/join", headers=u)
    assert (await client.post(f"/v1/common-challenges/{cid}/certify", headers=u)).status_code == 201
    async with db_session() as s:
        assert (await s.execute(select(CommonChallengeCert.steps))).scalar_one() is None


async def test_예정과_종료_챌린지는_인증할_수_없고_종료된_챌린지는_참여도_못_한다(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    _, u = await make(client, db_session, "u@test.kr", "초록접시")
    soon = (await open_challenge(client, admin, start=3, end=12))["challenge_id"]
    old = (await open_challenge(client, admin, start=-10, end=-1))["challenge_id"]
    assert (await client.post(f"/v1/common-challenges/{soon}/join", headers=u)).status_code == 201        # 시작 전에는 참여 가능
    r = await client.post(f"/v1/common-challenges/{soon}/certify", json={"steps": 9000}, headers=u)
    assert r.status_code == 409 and r.json()["error"]["code"] == "COMMON_CHALLENGE_NOT_ACTIVE"
    r = await client.post(f"/v1/common-challenges/{old}/join", headers=u)
    assert r.status_code == 409 and r.json()["error"]["code"] == "COMMON_CHALLENGE_ENDED"
    states = {i["challenge_id"]: i["state"] for i in (await client.get("/v1/common-challenges", headers=u)).json()["data"]["items"]}
    assert states == {soon: "upcoming", old: "ended"}
    only = (await client.get("/v1/common-challenges", params={"state": "upcoming"}, headers=u)).json()["data"]["items"]
    assert [i["challenge_id"] for i in only] == [soon]
    assert (await client.get("/v1/common-challenges/none", headers=u)).status_code == 404


async def _seed_certs(Session, cid: str, uid: str, days: int, last_at):
    """과거 날짜의 인증을 직접 넣는다 (마지막 인증 시각은 동점 처리 확인용으로 정한다)."""
    async with Session() as s:
        s.add(CommonChallengeParticipant(challenge_id=cid, user_id=uid, joined_at=utcnow()))
        for n in range(days):
            s.add(CommonChallengeCert(challenge_id=cid, user_id=uid, cert_date=today_kst() - timedelta(days=20 - n),
                                      created_at=last_at))
        await s.commit()


async def test_순위는_인증_일수_그다음_먼저_도달한_사람이다(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    ids, heads = {}, {}
    for nick in ("일등", "공동이", "공동삼", "넷째", "다섯째", "여섯째", "일곱째"):
        ids[nick], heads[nick] = await make(client, db_session, f"{nick}@test.kr", nick)
    cid = (await open_challenge(client, admin, start=-20, end=-11))["challenge_id"]       # 이미 끝난 10일 챌린지
    t0 = utcnow() - timedelta(days=15)
    plan = [("일등", 9, 0), ("공동이", 8, 1), ("공동삼", 8, 2), ("넷째", 7, 3), ("다섯째", 7, 4), ("여섯째", 3, 5), ("일곱째", 1, 6)]
    for nick, days, hours in plan:
        await _seed_certs(db_session, cid, ids[nick], days, t0 + timedelta(hours=hours))
    d = (await client.get(f"/v1/common-challenges/{cid}", headers=heads["일곱째"])).json()["data"]
    assert [(r["rank"], r["nickname"], r["days"]) for r in d["top"]] == [
        (1, "일등", 9), (2, "공동이", 8), (3, "공동삼", 8), (4, "넷째", 7), (5, "다섯째", 7), (7, "일곱째", 1)]   # 5위 밖이면 내 순위를 덧붙인다
    assert d["my_rank"] == 7 and d["top"][-1]["is_me"] is True and d["participants"] == 7
    assert d["state"] == "ended" and d["finalized"] is False


async def test_순위_확정은_끝난_뒤_한_번만_보상은_순위권과_완주자에게(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    ids = {}
    for nick in ("일등", "이등", "삼등", "넷째", "다섯째"):
        ids[nick], _ = await make(client, db_session, f"{nick}@test.kr", nick)
    # 진행 중인 챌린지는 확정할 수 없다
    running = (await open_challenge(client, admin))["challenge_id"]
    r = await client.post(f"/v1/admin/common-challenges/{running}/finalize", headers=admin)
    assert r.status_code == 409 and r.json()["error"]["code"] == "COMMON_CHALLENGE_NOT_ENDED"
    cid = (await open_challenge(client, admin, start=-20, end=-11))["challenge_id"]        # 10일, 완주 기준 7일
    t0 = utcnow() - timedelta(days=15)
    for hours, (nick, days) in enumerate([("일등", 10), ("이등", 9), ("삼등", 8), ("넷째", 7), ("다섯째", 6)]):
        await _seed_certs(db_session, cid, ids[nick], days, t0 + timedelta(hours=hours))
    res = (await client.post(f"/v1/admin/common-challenges/{cid}/finalize", headers=admin)).json()["data"]
    assert res == {"challenge_id": cid, "ranked": 3, "completed": 1, "total_pie": 300 + 200 + 100 + 20}
    async with db_session() as s:
        got = {n: [(e.reason, e.delta) for e in (await s.execute(select(PieLedger).where(PieLedger.user_id == ids[n], PieLedger.reason != "welcome"))).scalars()]
               for n in ids}
    assert got["일등"] == [("common_challenge_rank", 300)] and got["이등"] == [("common_challenge_rank", 200)]
    assert got["삼등"] == [("common_challenge_rank", 100)]                     # 순위 보상을 받으면 완주 보상은 따로 없다
    assert got["넷째"] == [("common_challenge_complete", 20)] and got["다섯째"] == []   # 다섯째는 6일 < 완주 기준 7일
    again = await client.post(f"/v1/admin/common-challenges/{cid}/finalize", headers=admin)
    assert again.status_code == 409 and again.json()["error"]["code"] == "COMMON_CHALLENGE_FINALIZED"
    # 확정한 뒤에는 고칠 수 없고, 화면에는 확정됨으로 보인다
    patch = await client.patch(f"/v1/admin/common-challenges/{cid}", json={"title": "바꾸기"}, headers=admin)
    assert patch.status_code == 409
    _, u = await make(client, db_session, "viewer@test.kr")
    assert (await client.get(f"/v1/common-challenges/{cid}", headers=u)).json()["data"]["finalized"] is True
    async with db_session() as s:
        assert sum(e.delta for e in (await s.execute(select(PieLedger))).scalars()) == 620 + 10 * 5   # 닉네임 시작 선물 10 x 5명


async def test_시작_전에는_보상과_이름을_고칠_수_있다(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    c = await open_challenge(client, admin, start=2, end=11)
    r = await client.patch(f"/v1/admin/common-challenges/{c['challenge_id']}",
                           json={"title": "열흘 걷기", "reward_first": 400, "complete_min_days": 8}, headers=admin)
    d = r.json()["data"]
    assert (d["title"], d["rewards"]["first"], d["complete_min_days"]) == ("열흘 걷기", 400, 8)
    assert (await client.patch(f"/v1/admin/common-challenges/{c['challenge_id']}", json={"complete_min_days": 11}, headers=admin)).status_code == 422
    assert (await client.patch(f"/v1/admin/common-challenges/{c['challenge_id']}", json={"starts_on": "2026-01-01"}, headers=admin)).status_code == 422   # 기간은 못 바꾼다
    assert (await client.patch("/v1/admin/common-challenges/none", json={"title": "x" * 3}, headers=admin)).status_code == 404


async def test_관리자_행위가_기록에_남는다(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    cid = (await open_challenge(client, admin, start=-20, end=-11))["challenge_id"]
    await client.get("/v1/admin/common-challenges", headers=admin)
    await client.patch(f"/v1/admin/common-challenges/{cid}", json={"title": "고친 이름"}, headers=admin)
    await client.post(f"/v1/admin/common-challenges/{cid}/finalize", headers=admin)
    async with db_session() as s:
        logs = {(a, t) for a, t in (await s.execute(select(AdminAuditLog.action, AdminAuditLog.target))).all()}
    assert {("common_challenge_create", cid[-8:]), ("common_challenges_view", None),
            ("common_challenge_update", cid[-8:]), ("common_challenge_finalize", cid[-8:])} <= logs


async def test_동의_철회는_참여와_인증과_파이를_지우고_탈퇴하면_순위에서_빠진다(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    uid, u = await make(client, db_session, "u@test.kr", "철회자")
    other_id, o = await make(client, db_session, "o@test.kr", "남는사람")
    cid = (await open_challenge(client, admin))["challenge_id"]
    for h in (u, o):
        await client.post(f"/v1/common-challenges/{cid}/join", headers=h)
        await client.post(f"/v1/common-challenges/{cid}/certify", json={"steps": 8000}, headers=h)
    async with db_session() as s:
        await account_service.delete_health_data(s, uid)
        await s.commit()
    async with db_session() as s:
        assert (await s.execute(select(CommonChallengeCert).where(CommonChallengeCert.user_id == uid))).scalars().all() == []
        assert (await s.execute(select(PieLedger).where(PieLedger.user_id == uid))).scalars().all() == []
        assert (await s.execute(select(CommonChallengeCert).where(CommonChallengeCert.user_id == other_id))).scalars().all() != []
    top = (await client.get(f"/v1/common-challenges/{cid}", headers=o)).json()["data"]
    assert [r["nickname"] for r in top["top"]] == ["남는사람"] and top["participants"] == 1


async def test_시작_전에는_기간과_걸음_수까지_고치고_시작한_뒤에는_제목과_보상만_고친다(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    today = today_kst()
    ahead = await open_challenge(client, admin, start=3, end=12)                  # 3일 뒤 시작
    r = await client.patch(f"/v1/admin/common-challenges/{ahead['challenge_id']}", headers=admin, json={
        "title": "고친 제목", "target_steps": 9000, "starts_on": str(today + timedelta(days=5)),
        "ends_on": str(today + timedelta(days=14)), "reward_first": 400})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["title"] == "고친 제목" and d["target_steps"] == 9000 and d["starts_on"] == str(today + timedelta(days=5))
    assert d["rewards"]["first"] == 400
    r = await client.patch(f"/v1/admin/common-challenges/{ahead['challenge_id']}", headers=admin,
                           json={"starts_on": str(today + timedelta(days=20))})           # 끝나는 날보다 늦다
    assert r.status_code == 422
    running = await open_challenge(client, admin, start=-2, end=7)                # 이미 시작
    r = await client.patch(f"/v1/admin/common-challenges/{running['challenge_id']}", headers=admin, json={"title": "진행 중에 고침"})
    assert r.status_code == 200
    r = await client.patch(f"/v1/admin/common-challenges/{running['challenge_id']}", headers=admin, json={"ends_on": str(today + timedelta(days=30))})
    assert r.status_code == 409 and r.json()["error"]["code"] == "COMMON_CHALLENGE_STARTED"


async def test_챌린지를_지우면_참여와_인증_기록도_함께_지워지고_확정한_것은_못_지운다(client, db_session):
    _, admin = await make(client, db_session, ADMIN)
    _, u = await make(client, db_session, "u@t.kr", "유저")
    c = await open_challenge(client, admin, start=-1, end=8)
    cid = c["challenge_id"]
    await client.post(f"/v1/common-challenges/{cid}/join", headers=u)
    await client.post(f"/v1/common-challenges/{cid}/certify", json={"steps": 8000}, headers=u)
    assert (await client.delete(f"/v1/admin/common-challenges/{cid}", headers=u)).status_code == 403    # 관리자만
    assert (await client.delete(f"/v1/admin/common-challenges/{cid}", headers=admin)).status_code == 204
    async with db_session() as s:
        assert (await s.execute(select(CommonChallengeCert))).scalars().all() == []
        assert (await s.execute(select(CommonChallengeParticipant))).scalars().all() == []
    assert (await client.get(f"/v1/common-challenges/{cid}", headers=u)).status_code == 404
    done = await open_challenge(client, admin, start=-9, end=-1)
    assert (await client.post(f"/v1/admin/common-challenges/{done['challenge_id']}/finalize", headers=admin)).status_code == 200
    r = await client.delete(f"/v1/admin/common-challenges/{done['challenge_id']}", headers=admin)
    assert r.status_code == 409 and r.json()["error"]["code"] == "COMMON_CHALLENGE_FINALIZED"


async def test_관리자가_문의를_지울_수_있다(client, db_session):
    from app.models.inquiry import Inquiry
    _, admin = await make(client, db_session, ADMIN)
    uid, u = await make(client, db_session, "u@t.kr", "유저")
    r = await client.post("/v1/inquiries", json={"title": "지울 문의", "body": "내용"}, headers=u)
    iid = r.json()["data"]["inquiry_id"]
    assert (await client.delete(f"/v1/admin/inquiries/{iid}", headers=u)).status_code == 403
    assert (await client.delete(f"/v1/admin/inquiries/{iid}", headers=admin)).status_code == 204
    assert (await client.delete(f"/v1/admin/inquiries/{iid}", headers=admin)).status_code == 404
    async with db_session() as s:
        assert (await s.execute(select(Inquiry))).scalars().all() == []
