"""관리자 챌린지 통계 테스트: 미션별 선택 수·완료율·포기율·평균 일수, 사이클 요약, 권한, 개인 식별 정보 없음."""
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.challenge import Challenge, ChallengeCycle, ChallengeLevel, ChallengeLog, CycleChallenge
from app.models.user import User, UserProfile
from tests.conftest import make_program

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 10, 12, 9, 0)


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@test.kr")


async def make_account(Session, email: str) -> tuple[dict, str]:
    async with Session() as s:
        user = User(email=email, password_hash="x", status="active")
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        return {"Authorization": f"Bearer {create_access_token(user.user_id)}"}, user.user_id


async def add_cycle(s, user_id: str, status: str, number: int = 1) -> ChallengeCycle:
    program = make_program(user_id, now=NOW)
    s.add(program)
    await s.flush()
    cyc = ChallengeCycle(user_id=user_id, program_id=program.program_id,cycle_number=number, started_on=date(2026, 9, 1), ended_on=date(2026, 9, 28),
                         status=status, created_at=NOW, updated_at=NOW)
    s.add(cyc)
    await s.flush()
    return cyc


async def add_mission(s, cyc: ChallengeCycle, code: str, selection_type: str, status: str, logs: list[str]):
    ch = (await s.execute(select(Challenge).where(Challenge.challenge_code == code))).scalar_one()
    lv = (await s.execute(select(ChallengeLevel).where(ChallengeLevel.challenge_id == ch.challenge_id))).scalars().first()
    cc = CycleChallenge(cycle_id=cyc.cycle_id, challenge_id=ch.challenge_id, selection_type=selection_type,
                        difficulty=lv.difficulty, weekly_target=lv.weekly_target, status=status)
    s.add(cc)
    await s.flush()
    for i, st in enumerate(logs):
        s.add(ChallengeLog(cycle_challenge_id=cc.cycle_challenge_id, log_date=date(2026, 9, 1) + timedelta(days=i),
                           status=st, recorded_at=NOW, updated_at=NOW))


@pytest_asyncio.fixture
async def seeded(db_session):
    """사이클 4개: 달성 1, 미달 1, 중단(포기) 1, 진행 중 1."""
    ids = []
    for n in range(4):
        _, uid = await make_account(db_session, f"u{n}@test.kr")
        ids.append(uid)
    async with db_session() as s:
        a = await add_cycle(s, ids[0], "completed")
        await add_mission(s, a, "SMK-1", "fixed", "completed", ["completed"] * 5)
        await add_mission(s, a, "NA-1", "selected", "completed", ["completed"] * 20 + ["failed"] * 3 + ["skipped"])
        b = await add_cycle(s, ids[1], "incomplete")
        await add_mission(s, b, "SMK-1", "fixed", "incomplete", ["completed"] * 2)
        await add_mission(s, b, "NA-1", "selected", "incomplete", ["completed"] * 10)
        c = await add_cycle(s, ids[2], "stopped")
        await add_mission(s, c, "SMK-1", "fixed", "stopped", [])
        await add_mission(s, c, "ACT-1", "selected", "stopped", ["completed"])
        d = await add_cycle(s, ids[3], "active")
        await add_mission(s, d, "SMK-1", "fixed", "active", ["completed"] * 3)
        await add_mission(s, d, "NA-1", "selected", "active", ["completed"] * 5)
        await s.commit()


async def stats(client, h) -> dict:
    r = await client.get("/v1/admin/stats/challenges", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    return {"missions": {m["challenge_code"]: m for m in d["missions"]}, "cycles": d["cycles"], "raw": d}


async def test_requires_admin(client, db_session):
    assert (await client.get("/v1/admin/stats/challenges")).status_code == 401
    h, _ = await make_account(db_session, "user@test.kr")
    r = await client.get("/v1/admin/stats/challenges", headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "ADMIN_FORBIDDEN"


async def test_empty_data_has_no_rates(client, db_session):
    h, _ = await make_account(db_session, "admin@test.kr")
    d = await stats(client, h)
    assert len(d["missions"]) == 10                      # 쓰이지 않은 미션도 0으로 보임
    assert all(m["assigned_count"] == 0 and m["completion_rate"] is None for m in d["missions"].values())
    assert d["cycles"]["total"] == 0 and d["cycles"]["completion_rate"] is None and d["cycles"]["users_started"] == 0


async def test_mission_stats(client, db_session, seeded):
    h, _ = await make_account(db_session, "admin@test.kr")
    d = await stats(client, h)
    na = d["missions"]["NA-1"]
    assert (na["assigned_count"], na["selected_count"]) == (3, 3)
    assert (na["active_count"], na["completed_count"], na["incomplete_count"], na["stopped_count"]) == (1, 1, 1, 0)
    assert na["completion_rate"] == 0.5 and na["giving_up_rate"] == 0.0
    assert na["avg_logged_days"] == 13.0 and na["avg_completed_days"] == 11.7      # (24+10+5)/3, (20+10+5)/3
    act = d["missions"]["ACT-1"]
    assert (act["selected_count"], act["stopped_count"]) == (1, 1)
    assert act["completion_rate"] is None and act["giving_up_rate"] == 1.0         # 끝까지 간 것이 없음 / 전부 포기
    smk = d["missions"]["SMK-1"]                                                   # 고정 미션: 선택 수는 0, 배정 수는 4
    assert (smk["assigned_count"], smk["selected_count"]) == (4, 0)
    assert (smk["completed_count"], smk["incomplete_count"], smk["stopped_count"], smk["active_count"]) == (1, 1, 1, 1)
    assert smk["completion_rate"] == 0.5 and smk["giving_up_rate"] == 0.333
    assert d["missions"]["WT-1"]["assigned_count"] == 0                            # 안 쓰인 미션


async def test_cycle_stats(client, db_session, seeded):
    h, _ = await make_account(db_session, "admin@test.kr")
    c = (await stats(client, h))["cycles"]
    assert (c["total"], c["active"], c["completed"], c["incomplete"], c["stopped"]) == (4, 1, 1, 1, 1)
    assert c["completion_rate"] == 0.5 and c["giving_up_rate"] == 0.333 and c["users_started"] == 4


async def test_no_personal_identifiers_in_response(client, db_session, seeded):
    h, uid = await make_account(db_session, "admin@test.kr")
    d = await stats(client, h)
    text = str(d["raw"])
    assert "@" not in text and uid not in text and "u0" not in text          # 이메일·사용자 번호 없음
    keys = {k for m in d["raw"]["missions"] for k in m} | set(d["raw"]["cycles"])
    assert not keys & {"user_id", "email", "cycle_id", "cycle_challenge_id"}  # 숫자와 이름만


async def test_withdrawn_users_drop_out_of_stats(client, db_session, seeded):
    """탈퇴하면 그 사용자의 챌린지 기록이 지워지므로 통계에서도 빠진다."""
    from app.services import account_service
    h, _ = await make_account(db_session, "admin@test.kr")
    async with db_session() as s:
        victim = (await s.execute(select(User).where(User.email == "u0@test.kr"))).scalar_one()
        await account_service.delete_account_data(s, victim)
        await s.commit()
    d = await stats(client, h)
    assert d["cycles"]["total"] == 3 and d["cycles"]["completed"] == 0 and d["cycles"]["users_started"] == 3
    assert d["missions"]["NA-1"]["selected_count"] == 2
