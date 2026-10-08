"""챌린지 API 흐름 테스트: 추천 → 시작 → 매일 기록 → 재로그인 조회 → 4주 종료 → 다음 사이클."""
from datetime import date, timedelta

import pytest

from app.services import challenge_service
from tests.conftest import make_user

pytestmark = pytest.mark.asyncio

DAY1 = date(2026, 10, 12)

SMOKER_DRINKER = {"SMOKING": "current", "ALCOHOL_FREQ": "2_3_per_week", "ALCOHOL_AMOUNT": "5_6",
                  "SBP": 145, "DBP": 92, "HEIGHT": 172, "WEIGHT": 78, "HTN_STATUS": "none", "DIABETES": "false"}
HIGH_NA = {"N0": ("salty", 50.0)} | {f"N{i}": ("very", 10.0) for i in range(1, 11)}
SURVEY = HIGH_NA | {"P1": ("none", None), "E1": ("rare", None), "B1": ("0", None)}


@pytest.fixture
def today(monkeypatch):
    state = {"d": DAY1}
    monkeypatch.setattr(challenge_service, "today_kst", lambda: state["d"])
    return state


async def test_full_cycle_flow(client, db_session, today):
    h = await make_user(db_session, measurements=SMOKER_DRINKER, answers=SURVEY)

    # 추천: 흡연·음주 고정 + 선택 후보
    r = await client.get("/v1/challenges/recommendations", headers=h)
    assert r.status_code == 200, r.text
    rec = r.json()["data"]
    assert [s["mission"]["code"] for s in rec["fixed"]] == ["SMK-1", "ALC-1"]
    codes = [c["code"] for c in rec["candidates"]]
    assert "NA-1" in codes and "BRK-1" in codes
    assert rec["fixed"][1]["mission"]["answers"][-1] == {"code": "3", "label": "3잔 이상"}  # 남성 선택지
    assert rec["cycle_number"] == 1 and rec["total_cycles"] == 3
    assert rec["sodium"]["sodium_grade"] in ("careful_high", "severe")

    assert "WT-1" in codes  # BMI 26.4
    # 후보가 아닌 미션은 시작 불가 (걸음 수를 몰라 ACT-1 제외)
    r = await client.post("/v1/challenges/cycles", json={"selected_code": "ACT-1"}, headers=h)
    assert r.status_code == 422

    r = await client.post("/v1/challenges/cycles", json={"selected_code": "NA-1"}, headers=h)
    assert r.status_code == 201, r.text
    cycle = r.json()["data"]
    assert cycle["started_on"] == "2026-10-12" and cycle["ended_on"] == "2026-11-08"
    assert sorted(m["card"]["code"] for m in cycle["missions"]) == ["ALC-1", "NA-1", "SMK-1"]
    assert cycle["missions"][-1]["card"]["code"] == "NA-1"  # 선택 미션이 마지막

    # 진행 중에는 새로 시작할 수 없음
    r = await client.post("/v1/challenges/cycles", json={"selected_code": "BRK-1"}, headers=h)
    assert r.status_code == 409

    # 매일 기록 + 같은 날 수정
    r = await client.put("/v1/challenges/cycles/current/logs/ALC-1", json={"answer": "3"}, headers=h)
    log = r.json()["data"]
    assert log["status"] == "failed" and log["limit_exceeded"] is True and log["warning"]
    r = await client.put("/v1/challenges/cycles/current/logs/ALC-1", json={"answer": "1"}, headers=h)
    assert r.json()["data"]["status"] == "completed"
    r = await client.put("/v1/challenges/cycles/current/logs/NA-1", json={"answer": "bad"}, headers=h)
    assert r.status_code == 422
    r = await client.put("/v1/challenges/cycles/current/logs/BRK-1", json={"answer": "ate"}, headers=h)
    assert r.status_code == 404  # 이번 사이클에 없는 미션

    # 다음 날 다시 로그인해도 어제 기록이 보이고, 오늘 기록은 비어 있음
    today["d"] = DAY1 + timedelta(days=1)
    r = await client.get("/v1/challenges/cycles/current", headers=h)
    cur = r.json()["data"]
    alc = next(m for m in cur["missions"] if m["card"]["code"] == "ALC-1")
    assert cur["day_number"] == 2 and alc["today_log"] is None
    assert alc["logs"][0]["log_date"] == "2026-10-12" and alc["weeks"][0]["completed"] == 1
    assert alc["streak"] == 1


async def test_cycle_closes_after_4_weeks_and_completed_mission_continues(client, db_session, today):
    h = await make_user(db_session, measurements=SMOKER_DRINKER, answers=SURVEY)
    await client.post("/v1/challenges/cycles", json={"selected_code": "NA-2"}, headers=h)

    # 28일 동안 NA-2만 매일 완료
    for i in range(28):
        today["d"] = DAY1 + timedelta(days=i)
        r = await client.put("/v1/challenges/cycles/current/logs/NA-2", json={"answer": "not_added"}, headers=h)
        assert r.status_code == 200, r.text

    # 29일째: 사이클이 닫힘 → 진행 중 없음, 이력에 incomplete (흡연·음주 미기록)
    today["d"] = DAY1 + timedelta(days=28)
    assert (await client.get("/v1/challenges/cycles/current", headers=h)).status_code == 404
    hist = (await client.get("/v1/challenges/cycles", headers=h)).json()["data"]
    assert hist[0]["status"] == "incomplete" and hist[0]["cycle_number"] == 1

    detail = (await client.get(f"/v1/challenges/cycles/{hist[0]['cycle_id']}", headers=h)).json()["data"]
    status = {m["card"]["code"]: m["status"] for m in detail["missions"]}
    assert status == {"SMK-1": "incomplete", "ALC-1": "incomplete", "NA-2": "completed"}

    # 다음 사이클: 2번째, 완료한 NA-2는 축하 표시와 함께 이어서 고를 수 있음
    rec = (await client.get("/v1/challenges/recommendations", headers=h)).json()["data"]
    assert rec["cycle_number"] == 2
    na2 = next(c for c in rec["candidates"] if c["code"] == "NA-2")
    assert na2["completed_before"] is True and rec["keep_going_message"]
    assert all(not c["completed_before"] for c in rec["candidates"] if c["code"] != "NA-2")
    r = await client.post("/v1/challenges/cycles", json={"selected_code": "NA-2"}, headers=h)
    assert r.status_code == 201 and r.json()["data"]["cycle_number"] == 2


async def test_stop_and_requirements(client, db_session, today):
    h = await make_user(db_session, measurements=SMOKER_DRINKER, answers=SURVEY)
    await client.post("/v1/challenges/cycles", json={"selected_code": "NA-1"}, headers=h)
    r = await client.post("/v1/challenges/cycles/current/stop", json={"reason_code": "too_hard"}, headers=h)
    assert r.json()["data"]["status"] == "stopped"
    # 중단한 사이클은 번호를 쓰지 않음
    rec = (await client.get("/v1/challenges/recommendations", headers=h)).json()["data"]
    assert rec["cycle_number"] == 1

    # 로그인 없이 / 건강정보 없이
    assert (await client.get("/v1/challenges/recommendations")).status_code == 401


async def test_survey_not_done_and_weight_mission(client, db_session, today):
    # 비흡연·비음주·BMI 27.8, 설문 안 함 → 나트륨 등은 "설문을 마치면 추천돼요", 체중 관리 후보
    h = await make_user(db_session, sex="female", birth=date(1995, 1, 1), measurements={
        "SMOKING": "never", "ALCOHOL_FREQ": "never_lifetime", "SBP": 120, "DBP": 78,
        "HEIGHT": 160, "WEIGHT": 71, "HTN_STATUS": "none", "DIABETES": "false"})
    rec = (await client.get("/v1/challenges/recommendations", headers=h)).json()["data"]
    assert [s["mission"] for s in rec["fixed"]] == [None, None]
    assert [c["code"] for c in rec["candidates"]] == ["WT-1"]
    assert {s["category"] for s in rec["survey_needed"]} == {"SODIUM", "ACTIVITY", "EATOUT", "BREAKFAST"}
    r = await client.post("/v1/challenges/cycles", json={"selected_code": "WT-1"}, headers=h)
    assert r.status_code == 201
    r = await client.put("/v1/challenges/cycles/current/logs/WT-1", json={"answer": "yes"}, headers=h)
    assert r.json()["data"]["status"] == "completed"


FULL = SMOKER_DRINKER | {"WAIST": 90, "TOTAL_CHOL": 210, "PARENT_HTN": "no"}


async def test_reassessment_and_review(client, db_session, today):
    h = await make_user(db_session, measurements=FULL, answers=SURVEY)
    basis_id = (await client.get("/v1/health/records", headers=h)).json()["data"][0]["health_record_id"]
    r = await client.post("/v1/predictions/jobs", json={"health_record_id": basis_id, "request_type": "initial"}, headers=h)
    assert r.status_code == 201, r.text

    cycle = (await client.post("/v1/challenges/cycles", json={"selected_code": "NA-1"}, headers=h)).json()["data"]
    cid = cycle["cycle_id"]
    body = {"measurements": [
        {"metric_code": "SBP", "value_num": 136}, {"metric_code": "DBP", "value_num": 86},
        {"metric_code": "WEIGHT", "value_num": 76}, {"metric_code": "WAIST", "value_num": 88},
        {"metric_code": "SMOKING", "value_code": "former"},
        {"metric_code": "ALCOHOL_FREQ", "value_code": "2_4_per_month"}, {"metric_code": "ALCOHOL_AMOUNT", "value_code": "1_2"},
    ]}

    # 4주가 끝나기 전에는 재입력 불가
    r = await client.post(f"/v1/challenges/cycles/{cid}/reassessment", json=body, headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "CHALLENGE_CYCLE_NOT_ENDED"

    today["d"] = DAY1 + timedelta(days=28)
    hist = (await client.get("/v1/challenges/cycles", headers=h)).json()["data"]
    assert hist[0]["reassessed"] is False

    # 필수 항목 빠짐 → 422
    r = await client.post(f"/v1/challenges/cycles/{cid}/reassessment",
                          json={"measurements": body["measurements"][:2]}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "REASSESSMENT_INCOMPLETE"
    # 다시 받지 않는 항목(키) → 422
    r = await client.post(f"/v1/challenges/cycles/{cid}/reassessment",
                          json={"measurements": body["measurements"] + [{"metric_code": "HEIGHT", "value_num": 180}]}, headers=h)
    assert r.status_code == 422

    r = await client.post(f"/v1/challenges/cycles/{cid}/reassessment", json=body, headers=h)
    assert r.status_code == 201, r.text
    rv = r.json()["data"]
    assert rv["reassessed"] is True
    assert (rv["before"]["sbp"], rv["after"]["sbp"]) == (145, 136)
    assert (rv["before"]["weight_kg"], rv["after"]["weight_kg"]) == (78, 76)
    assert (rv["before"]["smoking"], rv["after"]["smoking"]) == ("current", "former")
    assert rv["normal_weight_range"] == [55, 68] and rv["waist_limit"] == 90  # 키 172
    assert rv["bp_note"]
    assert [m["code"] for m in rv["missions"]] == ["SMK-1", "ALC-1", "NA-1"]
    models = {m["model_code"]: m for m in rv["models"]}
    assert models["MODEL_A"]["comparable"] is True and models["MODEL_B"]["comparable"] is True
    assert models["MODEL_A"]["after_probability"] != models["MODEL_A"]["before_probability"]

    # 다시 받지 않은 항목은 재예측 때 직전 값(carried_forward)으로 새 기록에 들어감
    from sqlalchemy import select
    from app.models.health import HealthMeasurement, HealthRecord
    async with db_session() as s:
        rec = (await s.execute(select(HealthRecord).where(HealthRecord.cycle_id == cid))).scalar_one()
        ms = {m.metric_code: m for m in (await s.execute(
            select(HealthMeasurement).where(HealthMeasurement.health_record_id == rec.health_record_id))).scalars()}
    assert ms["TOTAL_CHOL"].input_method == "carried_forward" and ms["TOTAL_CHOL"].value_num == 210
    assert ms["HEIGHT"].input_method == "carried_forward"  # 이월은 예측 서비스(_carry_forward)가 채움
    assert ms["SBP"].input_method == "manual"

    # 두 번은 안 됨, 이력에 재입력 완료 표시
    r = await client.post(f"/v1/challenges/cycles/{cid}/reassessment", json=body, headers=h)
    assert r.status_code == 409
    assert (await client.get("/v1/challenges/cycles", headers=h)).json()["data"][0]["reassessed"] is True
    assert (await client.get(f"/v1/challenges/cycles/{cid}/review", headers=h)).json()["data"]["after"]["dbp"] == 86

    # 다음 사이클 추천은 4주 재입력 값으로 판정 (흡연 → 과거 흡연, 음주 1–2잔 → 고정 칸 대체)
    rec2 = (await client.get("/v1/challenges/recommendations", headers=h)).json()["data"]
    assert [s["selection_type"] for s in rec2["fixed"]] == ["replacement", "replacement"]
    assert rec2["cycle_number"] == 2


async def test_step_count_answer_enables_act1(client, db_session, today):
    # P2 걸음 수 숫자 답 → ACT-1 후보, 목표 = 평소 + 2,000보
    h = await make_user(db_session, measurements=SMOKER_DRINKER, answers=SURVEY | {"P2": (None, 5300)})
    rec = (await client.get("/v1/challenges/recommendations", headers=h)).json()["data"]
    assert "ACT-1" in [c["code"] for c in rec["candidates"]]
    cycle = (await client.post("/v1/challenges/cycles", json={"selected_code": "ACT-1"}, headers=h)).json()["data"]
    act1 = next(m for m in cycle["missions"] if m["card"]["code"] == "ACT-1")
    assert act1["target_config"]["steps_target"] == 7300
    r = await client.put("/v1/challenges/cycles/current/logs/ACT-1", json={"quantity": 7400}, headers=h)
    assert r.json()["data"]["status"] == "completed"


async def test_data_export_includes_challenge_missions_and_logs(client, db_session, today):
    # 내 데이터 내려받기에 챌린지 미션·매일 기록도 들어간다 (개인정보 열람권)
    h = await make_user(db_session, measurements=SMOKER_DRINKER, answers=SURVEY)
    await client.post("/v1/challenges/cycles", json={"selected_code": "NA-1"}, headers=h)
    await client.put("/v1/challenges/cycles/current/logs/NA-1", json={"answer": "left"}, headers=h)
    await client.put("/v1/challenges/cycles/current/logs/SMK-1", json={"answer": "not_smoked"}, headers=h)
    exp = (await client.get("/v1/users/me/data-export", headers=h)).json()["data"]
    assert len(exp["challenge_cycles"]) == 1
    assert len(exp["cycle_challenges"]) == 3
    assert len(exp["challenge_logs"]) == 2
