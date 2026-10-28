"""12주 처음(0주) ↔ 마지막(12주) 비교 (GET /v1/challenges/program/review)."""
from datetime import date, datetime, timedelta

import pytest

from app.core.security import create_access_token
from app.models.challenge import ChallengeCycle
from app.models.health import HealthMeasurement, HealthRecord
from app.models.prediction import Prediction, PredictionJob
from app.models.user import User, UserProfile
from tests.conftest import make_program
from sqlalchemy import select

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 7, 1, 3, 0)
START = date(2026, 7, 1)
SNAPSHOT = {"age": 45, "sex": "M", "sbp": 150, "dbp": 95, "total_chol": 212, "smoking": "current",
            "diabetes": False, "htn_status": "none", "height_cm": 172, "weight_kg": 80, "waist_cm": 92,
            "parent_htn": "yes", "drink_freq": "2_3_per_week", "drink_amount": "5_6"}


async def _record(s, uid, input_type, day, sbp, weight, cycle_id=None):
    r = HealthRecord(user_id=uid, health_schema_id="schema-1", cycle_id=cycle_id, input_type=input_type,
                     examination_date=day, created_at=NOW)
    s.add(r)
    await s.flush()
    for code, v in (("SBP", sbp), ("DBP", sbp - 55), ("WEIGHT", weight), ("WAIST", 90)):
        s.add(HealthMeasurement(health_record_id=r.health_record_id, metric_code=code, value_num=v, measured_on=day, created_at=NOW))
    return r


async def _prediction(s, uid, record, version, score, snapshot):
    job = PredictionJob(user_id=uid, health_record_id=record.health_record_id, request_type="initial",
                        status="completed", requested_at=NOW, completed_at=NOW, input_snapshot=snapshot)
    s.add(job)
    await s.flush()
    s.add(Prediction(prediction_job_id=job.prediction_job_id, user_id=uid, model_code="MODEL_A",
                     model_version=version, status="completed", score=score, risk_level="high", predicted_at=NOW))


async def _user(Session, cycles_done: int):
    """처음 입력 + 사이클 cycles_done개(각각 끝 재입력)를 마친 사람."""
    async with Session() as s:
        u = User(email="p@test.kr", password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1981, 3, 1)))
        program = make_program(u.user_id, now=NOW)
        s.add(program)
        await s.flush()
        base = await _record(s, u.user_id, "initial", START - timedelta(days=1), 150, 80)
        await _prediction(s, u.user_id, base, "0.2.0", 0.9, SNAPSHOT)          # 처음 분석은 예전 모델
        final = None
        for n in range(1, cycles_done + 1):
            c = ChallengeCycle(user_id=u.user_id, program_id=program.program_id, cycle_number=n, started_on=START + timedelta(days=28 * (n - 1)),
                               ended_on=START + timedelta(days=28 * n - 1), status="completed", created_at=NOW, updated_at=NOW)
            s.add(c)
            await s.flush()
            final = await _record(s, u.user_id, "interim_reassessment", START + timedelta(days=28 * n),
                                  150 - 5 * n, 80 - n, cycle_id=c.cycle_id)
        if final is not None:
            await _prediction(s, u.user_id, final, "0.2.0", 0.5, {**SNAPSHOT, "sbp": 135, "weight_kg": 77})
        await s.commit()
        return {"Authorization": f"Bearer {create_access_token(u.user_id)}"}


async def test_12주를_마치면_처음과_12주를_같은_모델로_비교한다(client, db_session):
    h = await _user(db_session, 3)
    r = await client.get("/v1/challenges/program/review", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["weeks_done"] == 12
    assert (d["before"]["sbp"], d["after"]["sbp"]) == (150, 135)
    assert [c["week"] for c in d["checkpoints"]] == [0, 4, 8, 12]               # 혈압 선 그래프 4점
    assert [c["sbp"] for c in d["checkpoints"]] == [150, 145, 140, 135]
    assert [c["cycle_number"] for c in d["cycles"]] == [1, 2, 3]
    a = next(m for m in d["models"] if m["model_code"] == "MODEL_A")
    assert a["comparable"] is True and a["reason"] is None
    assert a["before_probability"] == 0.9
    assert a["before_probability"] > a["after_probability"]
    assert d["model_version"] == "0.2.0"


async def test_12주를_못_채워도_지금까지를_보여_준다(client, db_session):
    h = await _user(db_session, 1)                                              # 1차 재입력만 함 (중단·미완료)
    r = await client.get("/v1/challenges/program/review", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["weeks_done"] == 4
    assert [c["week"] for c in d["checkpoints"]] == [0, 4]
    assert (d["before"]["sbp"], d["after"]["sbp"]) == (150, 145)


async def test_재입력이_하나도_없으면_아직_볼_수_없다(client, db_session):
    h = await _user(db_session, 0)
    r = await client.get("/v1/challenges/program/review", headers=h)
    assert r.status_code == 404 and r.json()["error"]["code"] == "PROGRAM_REVIEW_NOT_READY"

async def test_program_번호로_지난_12주_결과를_조회한다(client, db_session):
    # 프로그램 1은 재입력까지 마쳐서 조회 가능하게 만든다.
    h = await _user(db_session, 1)

    # 같은 사용자의 프로그램 2는 새로 만들되 아직 사이클·재입력은 없다.
    async with db_session() as s:
        uid = (
            await s.execute(
                select(User.user_id).where(User.email == "p@test.kr")
            )
        ).scalar_one()

        program2 = make_program(
            uid,
            program_number=2,
            now=NOW + timedelta(days=100),
        )
        s.add(program2)
        await s.commit()

    # 최신 프로그램은 2번이지만, 1번을 지정하면 이전 결과가 나온다.
    r = await client.get("/v1/challenges/program/review?program=1", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["program_number"] == 1

    # 2번은 아직 재입력이 없으므로, 1번 결과를 잘못 돌려주면 안 된다.
    r = await client.get("/v1/challenges/program/review?program=2", headers=h)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "PROGRAM_REVIEW_NOT_READY"