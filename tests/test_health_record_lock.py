"""챌린지를 시작한 뒤에는 그 기준이 된 건강기록(처음 입력)을 고칠 수 없다."""
from datetime import date, datetime

import pytest

from app.core.security import create_access_token
from app.models.challenge import ChallengeCycle
from app.models.user import User, UserProfile
from tests.conftest import make_program

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 10, 1, 3, 0)


async def _user(Session):
    async with Session() as s:
        u = User(email="l@test.kr", password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        return u.user_id, {"Authorization": f"Bearer {create_access_token(u.user_id)}"}


async def _record(client, h, input_type, day):
    r = await client.post("/v1/health/records", json={"input_type": input_type, "examination_date": day}, headers=h)
    return r.json()["data"]["health_record_id"]


async def _put(client, h, rid, sbp):
    return await client.post(f"/v1/health/records/{rid}/measurements",
                             json={"measurements": [{"metric_code": "SBP", "value_num": sbp}]}, headers=h)


async def _start_cycle(Session, uid, day):
    async with Session() as s:
        program = make_program(uid, now=NOW)
        s.add(program)
        await s.flush()
        s.add(ChallengeCycle(user_id=uid,  program_id=program.program_id,cycle_number=1, started_on=day, ended_on=date(2026, 10, 30),
                             status="active", created_at=NOW, updated_at=NOW))
        await s.commit()


async def test_챌린지_시작_전에는_처음_입력을_고칠_수_있다(client, db_session):
    _, h = await _user(db_session)
    rid = await _record(client, h, "initial", "2026-10-01")
    assert (await _put(client, h, rid, 142)).status_code == 201
    assert (await _put(client, h, rid, 140)).status_code == 201           # 오타 고치기


async def test_챌린지를_시작하면_처음_입력을_고칠_수_없다(client, db_session):
    uid, h = await _user(db_session)
    rid = await _record(client, h, "initial", "2026-10-01")
    assert (await _put(client, h, rid, 142)).status_code == 201
    await _start_cycle(db_session, uid, date(2026, 10, 3))
    r = await _put(client, h, rid, 118)
    assert r.status_code == 409 and r.json()["error"]["code"] == "HEALTH_RECORD_LOCKED"
    detail = (await client.get(f"/v1/health/records/{rid}", headers=h)).json()["data"]
    assert any(m["metric_code"] == "SBP" and m["value_num"] == 142 for m in detail["measurements"])   # 처음 값 그대로


async def test_시작_뒤_기록과_주간_혈압은_그대로_쓸_수_있다(client, db_session):
    uid, h = await _user(db_session)
    await _record(client, h, "initial", "2026-10-01")
    await _start_cycle(db_session, uid, date(2026, 10, 3))
    weekly = await _record(client, h, "weekly_bp", "2026-10-10")
    assert (await _put(client, h, weekly, 130)).status_code == 201
    later = await _record(client, h, "interim_reassessment", "2026-10-31")    # 사이클 끝 재입력
    assert (await _put(client, h, later, 128)).status_code == 201