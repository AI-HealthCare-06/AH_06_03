"""지인 체험 자동 채움: DEMO_AUTOFILL이 켜져 있을 때만, 3일치 기록으로 나머지 4주를 채우고 사이클을 끝낸다."""
from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.services import challenge_service
from tests.conftest import make_user
from tests.test_challenge_api import DAY1, FULL, SURVEY

pytestmark = pytest.mark.asyncio

BODY = {"measurements": [
    {"metric_code": "SBP", "value_num": 136}, {"metric_code": "DBP", "value_num": 86},
    {"metric_code": "WEIGHT", "value_num": 76}, {"metric_code": "WAIST", "value_num": 88},
    {"metric_code": "SMOKING", "value_code": "former"},
    {"metric_code": "ALCOHOL_FREQ", "value_code": "2_4_per_month"}, {"metric_code": "ALCOHOL_AMOUNT", "value_code": "1_2"},
]}


@pytest.fixture
def today(monkeypatch):
    state = {"d": DAY1}
    monkeypatch.setattr(challenge_service, "today_kst", lambda: state["d"])
    return state


async def start_and_log_days(client, db_session, today, days: int):
    h = await make_user(db_session, measurements=FULL, answers=SURVEY)
    basis = (await client.get("/v1/health/records", headers=h)).json()["data"][0]["health_record_id"]
    assert (await client.post("/v1/predictions/jobs", json={"health_record_id": basis, "request_type": "initial"}, headers=h)).status_code == 201
    cid = (await client.post("/v1/challenges/cycles", json={"selected_code": "NA-2"}, headers=h)).json()["data"]["cycle_id"]
    results = []
    for i in range(days):
        today["d"] = DAY1 + timedelta(days=i)
        r = await client.put("/v1/challenges/cycles/current/logs/NA-2", json={"answer": "not_added"}, headers=h)
        assert r.status_code == 200, r.text
        results.append(r.json()["data"])
    return h, cid, results


async def test_꺼져_있으면_3일치를_남겨도_채우지_않는다(client, db_session, today):
    h, cid, results = await start_and_log_days(client, db_session, today, 3)
    assert all(r["autofilled"] is False for r in results)
    assert (await client.get("/v1/challenges/cycles/current", headers=h)).status_code == 200   # 아직 진행 중


async def test_켜져_있으면_3일째_기록에서_채우고_사이클이_끝난다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    h, cid, results = await start_and_log_days(client, db_session, today, 3)
    assert [r["autofilled"] for r in results] == [False, False, True]

    # 사이클이 닫히고(진행 중 없음), 채운 날을 포함해 NA-2가 달성 기준을 넘는다
    assert (await client.get("/v1/challenges/cycles/current", headers=h)).status_code == 404
    detail = (await client.get(f"/v1/challenges/cycles/{cid}", headers=h)).json()["data"]
    assert detail["status"] in ("completed", "incomplete")
    assert {m["card"]["code"]: m["status"] for m in detail["missions"]}["NA-2"] == "completed"
    assert detail["ended_on"] == (DAY1 + timedelta(days=2)).isoformat()      # 오늘(3일째)이 마지막 날
    assert date.fromisoformat(detail["started_on"]) == DAY1 + timedelta(days=2) - timedelta(days=27)

    # 4주 재입력과 전·후 비교가 바로 열린다
    r = await client.post(f"/v1/challenges/cycles/{cid}/reassessment", json=BODY, headers=h)
    assert r.status_code == 201, r.text


async def test_한_사이클에_한_번만_채운다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    h, cid, results = await start_and_log_days(client, db_session, today, 3)
    r = await client.put("/v1/challenges/cycles/current/logs/NA-2", json={"answer": "not_added"}, headers=h)
    assert r.status_code == 404      # 이미 끝난 사이클이라 더 기록할 수 없다


async def test_28일을_모두_채우고_달성_비율을_따른다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    h = await make_user(db_session, measurements=FULL, answers=SURVEY)
    basis = (await client.get("/v1/health/records", headers=h)).json()["data"][0]["health_record_id"]
    await client.post("/v1/predictions/jobs", json={"health_record_id": basis, "request_type": "initial"}, headers=h)
    cid = (await client.post("/v1/challenges/cycles", json={"selected_code": "NA-2"}, headers=h)).json()["data"]["cycle_id"]
    for i, ans in enumerate(["not_added", "added", "not_added"]):       # 3일 중 2일 완료
        today["d"] = DAY1 + timedelta(days=i)
        r = await client.put("/v1/challenges/cycles/current/logs/NA-2", json={"answer": ans}, headers=h)
    assert r.json()["data"]["autofilled"] is True

    from sqlalchemy import select
    from app.models.challenge import Challenge, ChallengeLog, CycleChallenge
    async with db_session() as s:
        rows = (await s.execute(
            select(Challenge.challenge_code, ChallengeLog.log_date, ChallengeLog.status)
            .join(CycleChallenge, CycleChallenge.cycle_challenge_id == ChallengeLog.cycle_challenge_id)
            .join(Challenge, Challenge.challenge_id == CycleChallenge.challenge_id)
            .where(CycleChallenge.cycle_id == cid))).all()
    for code in {c for c, _, _ in rows}:                                  # 모든 미션이 28일 모두 기록을 가진다
        assert len({d for c, d, _ in rows if c == code}) == 28, code
    na2 = [st for c, _, st in rows if c == "NA-2"]
    assert na2.count("completed") == 19 and na2.count("failed") == 9      # 3일 중 2일 → 28일 중 약 19일 완료
