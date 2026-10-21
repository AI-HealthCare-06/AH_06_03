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


ANSWERS = {"SMK-1": "not_smoked", "ALC-1": "1", "NA-2": "not_added"}


async def log_day(client, h, answers=ANSWERS):
    """그날 미션을 기록한다. 마지막 응답을 돌려준다."""
    last = None
    for code, ans in answers.items():
        last = await client.put(f"/v1/challenges/cycles/current/logs/{code}", json={"answer": ans}, headers=h)
        assert last.status_code == 200, last.text
    return last.json()["data"]


async def start_and_log_days(client, db_session, today, days: int):
    h = await make_user(db_session, measurements=FULL, answers=SURVEY)
    basis = (await client.get("/v1/health/records", headers=h)).json()["data"][0]["health_record_id"]
    assert (await client.post("/v1/predictions/jobs", json={"health_record_id": basis, "request_type": "initial"}, headers=h)).status_code == 201
    cid = (await client.post("/v1/challenges/cycles", json={"selected_code": "NA-2"}, headers=h)).json()["data"]["cycle_id"]
    results = []
    for i in range(days):
        today["d"] = DAY1 + timedelta(days=i)
        results.append(await log_day(client, h))
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
    assert detail["status"] == "completed"       # 3일 모두 완료했으니 나머지도 완료로 채워져 4주 완주
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
    day_answers = [ANSWERS, {**ANSWERS, "NA-2": "added"}, ANSWERS]       # NA-2만 3일 중 2일 완료
    for i, ans in enumerate(day_answers):
        today["d"] = DAY1 + timedelta(days=i)
        r = await log_day(client, h, ans)
    assert r["autofilled"] is True

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


async def test_첫_미션만_기록한_3일째에는_채우지_않고_모두_기록하면_채운다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    h, cid, _ = await start_and_log_days(client, db_session, today, 2)
    today["d"] = DAY1 + timedelta(days=2)
    codes = list(ANSWERS)
    for code in codes[:-1]:                      # 3일째에 미션 일부만 기록 → 아직 진행 중
        r = await client.put(f"/v1/challenges/cycles/current/logs/{code}", json={"answer": ANSWERS[code]}, headers=h)
        assert r.json()["data"]["autofilled"] is False
    assert (await client.get("/v1/challenges/cycles/current", headers=h)).status_code == 200
    r = await client.put(f"/v1/challenges/cycles/current/logs/{codes[-1]}", json={"answer": ANSWERS[codes[-1]]}, headers=h)
    assert r.json()["data"]["autofilled"] is True      # 마지막 미션까지 기록하면 채운다


async def test_채운_날에도_파이_보상을_준다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    h, cid, _ = await start_and_log_days(client, db_session, today, 3)
    pie = (await client.get("/v1/pie", headers=h)).json()["data"]
    balance = pie.get("balance", pie.get("count", pie.get("total")))
    assert balance is not None and balance > 100, pie      # 28일 중 기록 보상(+5·+10)과 완주 +50이 모두 들어옴


async def test_처음_입력이_여러_번이어도_채울_때_오류가_나지_않는다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    h = await make_user(db_session, measurements=FULL, answers=SURVEY)
    basis = (await client.get("/v1/health/records", headers=h)).json()["data"][0]["health_record_id"]
    await client.post("/v1/predictions/jobs", json={"health_record_id": basis, "request_type": "initial"}, headers=h)
    await client.post("/v1/challenges/cycles", json={"selected_code": "NA-2"}, headers=h)
    # 챌린지 시작 뒤에 처음 입력을 다른 날짜로 한 번 더 만든 경우(둘 다 시작일 이후로 옮겨질 수 있는 상황)
    for i in range(3):
        today["d"] = DAY1 + timedelta(days=i)
        if i == 1:
            r = await client.post("/v1/health/records", json={"input_type": "initial", "examination_date": today["d"].isoformat()}, headers=h)
            assert r.status_code in (201, 409), r.text
        r = await log_day(client, h)
    assert r["autofilled"] is True          # 500이 나지 않고 정상으로 채워짐
