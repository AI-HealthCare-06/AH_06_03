"""지인 체험 자동 채움: DEMO_AUTOFILL이 켜져 있을 때만, 서로 다른 3일을 기록하면 나머지 4주를 채우고 사이클을 끝낸다."""
from datetime import date, timedelta

import pytest

from app.core.config import settings
from app.services import challenge_service, demo_autofill_service
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


def force(monkeypatch, pattern):
    async def _next(_db):
        return pattern
    monkeypatch.setattr(demo_autofill_service, "next_pattern", _next)


ANSWERS = {"SMK-1": "not_smoked", "ALC-1": "1", "NA-2": "not_added"}


async def log_day(client, h, answers=ANSWERS):
    """그날 미션을 기록한다. 마지막 응답을 돌려준다."""
    last = None
    for code, ans in answers.items():
        last = await client.put(f"/v1/challenges/cycles/current/logs/{code}", json={"answer": ans}, headers=h)
        assert last.status_code == 200, last.text
    return last.json()["data"]


_KEEP: list = []


async def start_and_log_days(client, db_session, today, days: int):
    _KEEP.extend([dict(FULL), dict(SURVEY)])      # make_user가 id()로 이메일·설문 버전을 만들어서, 사용자마다 다른 dict가 필요하다
    h = await make_user(db_session, measurements=_KEEP[-2], answers=_KEEP[-1])
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


@pytest.mark.parametrize("pattern,status", [("steady", "completed"), ("wobble", "completed"), ("fade", "incomplete")])
async def test_패턴대로_채우고_사이클이_끝난다(client, db_session, today, monkeypatch, pattern, status):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    force(monkeypatch, pattern)
    h, cid, results = await start_and_log_days(client, db_session, today, 3)
    assert [r["autofilled"] for r in results] == [False, False, True]
    assert results[-1]["autofill_pattern"] == pattern

    # 사이클이 닫힌다(진행 중 없음). 꾸준함·흔들림은 완주, 미완료는 목표 미달로 끝난다
    assert (await client.get("/v1/challenges/cycles/current", headers=h)).status_code == 404
    detail = (await client.get(f"/v1/challenges/cycles/{cid}", headers=h)).json()["data"]
    assert detail["status"] == status
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


async def test_28일을_모두_채우고_흔들림은_2_3주차만_주_6일이다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    force(monkeypatch, "wobble")
    h, cid, results = await start_and_log_days(client, db_session, today, 3)
    assert results[-1]["autofilled"] is True

    from sqlalchemy import select
    from app.models.challenge import Challenge, ChallengeLog, CycleChallenge, ChallengeCycle
    async with db_session() as s:
        start = (await s.execute(select(ChallengeCycle.started_on).where(ChallengeCycle.cycle_id == cid))).scalar_one()
        rows = (await s.execute(
            select(Challenge.challenge_code, ChallengeLog.log_date, ChallengeLog.status)
            .join(CycleChallenge, CycleChallenge.cycle_challenge_id == ChallengeLog.cycle_challenge_id)
            .join(Challenge, Challenge.challenge_id == CycleChallenge.challenge_id)
            .where(CycleChallenge.cycle_id == cid))).all()
    for code in {c for c, _, _ in rows}:                                  # 모든 미션이 28일 모두 기록을 가진다
        assert len({d for c, d, _ in rows if c == code}) == 28, code
    done_by_week = [0, 0, 0, 0]
    for c, d, st in rows:
        if c == "NA-2" and st == "completed":
            done_by_week[(d - start).days // 7] += 1
    # 흔들림: 2·3주차만 주 6일, 나머지 주는 매일
    assert done_by_week == [7, 6, 6, 7], done_by_week


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
    force(monkeypatch, "steady")
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


async def test_비교_화면_응답에_채운_패턴이_들어간다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    force(monkeypatch, "wobble")
    h, cid, _ = await start_and_log_days(client, db_session, today, 3)
    await client.post(f"/v1/challenges/cycles/{cid}/reassessment", json=BODY, headers=h)
    rv = (await client.get(f"/v1/challenges/cycles/{cid}/review", headers=h)).json()["data"]
    assert rv["demo_fill"] == "wobble"


async def test_자동_채움이_없던_사이클은_표시가_없다(client, db_session, today):
    h, cid, _ = await start_and_log_days(client, db_session, today, 3)      # DEMO_AUTOFILL 꺼짐
    today["d"] = DAY1 + timedelta(days=28)
    await client.post(f"/v1/challenges/cycles/{cid}/reassessment", json=BODY, headers=h)
    rv = (await client.get(f"/v1/challenges/cycles/{cid}/review", headers=h)).json()["data"]
    assert rv["demo_fill"] is None


def test_미완료는_주간_목표가_3_5_7인_미션_모두_목표_미달이고_나머지는_완주다():
    from app.services import challenge_rules as rules
    for pattern, days in demo_autofill_service.PATTERNS.items():
        for target in (3, 5, 7):
            done = [demo_autofill_service.week_goal(pattern, d, target) for d in days]
            done[3] = max(done[3], 3)                      # 4주차에는 직접 한 3일이 들어 있다
            rate = sum(min(x, target) / target for x in done) / 4
            assert (rate >= 0.8) == (pattern != "fade"), (pattern, target, done, rate)


async def test_채운_순서대로_꾸준함_흔들림_미완료를_돌아가며_배정한다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    got = []
    for _ in range(4):
        _, _, results = await start_and_log_days(client, db_session, today, 3)
        got.append(results[-1]["autofill_pattern"])
    assert got == ["steady", "wobble", "fade", "steady"]


async def test_세_번째_기록일이_지나면_더_기록할_수_없다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    h, cid, _ = await start_and_log_days(client, db_session, today, 2)
    today["d"] = DAY1 + timedelta(days=2)
    await client.put("/v1/challenges/cycles/current/logs/SMK-1", json={"answer": "not_smoked"}, headers=h)   # 3번째 기록일, 일부만 기록
    today["d"] = DAY1 + timedelta(days=3)
    r = await client.put("/v1/challenges/cycles/current/logs/NA-2", json={"answer": "not_added"}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DEMO_RECORDING_CLOSED", r.text
    cur = (await client.get("/v1/challenges/cycles/current", headers=h)).json()["data"]
    assert cur["demo"]["phase"] == "finish_only" and cur["demo"]["record_days"] == 3


async def test_결과_보기_버튼은_미션이_남아_있으면_확인을_받고_마치면_채운다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    h, cid, _ = await start_and_log_days(client, db_session, today, 2)
    r = await client.post("/v1/challenges/cycles/current/demo-finish", json={}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DEMO_NOT_READY"     # 2일은 모자람

    today["d"] = DAY1 + timedelta(days=2)
    await client.put("/v1/challenges/cycles/current/logs/SMK-1", json={"answer": "not_smoked"}, headers=h)
    cur = (await client.get("/v1/challenges/cycles/current", headers=h)).json()["data"]
    assert cur["demo"]["phase"] == "finish_today" and cur["demo"]["unlogged_today"] == 2
    r = await client.post("/v1/challenges/cycles/current/demo-finish", json={}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DEMO_MISSIONS_UNLOGGED"
    r = await client.post("/v1/challenges/cycles/current/demo-finish", json={"confirm": True}, headers=h)
    assert r.status_code == 200 and r.json()["data"]["autofill_pattern"] in demo_autofill_service.PATTERNS
    assert (await client.get("/v1/challenges/cycles/current", headers=h)).status_code == 404
    assert (await client.post(f"/v1/challenges/cycles/{cid}/reassessment", json=BODY, headers=h)).status_code == 201


async def test_세_번째_기록일이_지난_뒤에도_결과_보기로_채울_수_있다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    h, cid, _ = await start_and_log_days(client, db_session, today, 2)
    today["d"] = DAY1 + timedelta(days=2)
    await client.put("/v1/challenges/cycles/current/logs/SMK-1", json={"answer": "not_smoked"}, headers=h)
    today["d"] = DAY1 + timedelta(days=3)
    r = await client.post("/v1/challenges/cycles/current/demo-finish", json={}, headers=h)      # 오늘은 기록일이 아니라 확인 없이
    assert r.status_code == 200, r.text
    detail = (await client.get(f"/v1/challenges/cycles/{cid}", headers=h)).json()["data"]
    assert detail["ended_on"] == (DAY1 + timedelta(days=3)).isoformat()


async def test_체험_마지막_날이_지나면_채우지_않고_종료_상태를_알린다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    monkeypatch.setattr(settings, "DEMO_AUTOFILL_END", (DAY1 + timedelta(days=1)).isoformat())
    h, cid, results = await start_and_log_days(client, db_session, today, 3)      # 3일째는 마지막 날 다음 날
    assert results[-1]["autofilled"] is False
    st = (await client.get("/v1/challenges/demo", headers=h)).json()["data"]
    assert st == {"enabled": True, "ended": True, "ends_on": (DAY1 + timedelta(days=1)).isoformat(), "has_result": False}
    r = await client.post("/v1/challenges/cycles/current/demo-finish", json={}, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DEMO_NOT_AVAILABLE"


async def test_채운_사람은_결과를_받았다고_나온다(client, db_session, today, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_AUTOFILL", True)
    h, cid, _ = await start_and_log_days(client, db_session, today, 3)
    st = (await client.get("/v1/challenges/demo", headers=h)).json()["data"]
    assert st["has_result"] is True and st["ended"] is False
