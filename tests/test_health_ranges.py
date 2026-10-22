"""터무니없는 건강정보(키 300cm, 몸무게 500kg, 혈압 1100/3)는 서버가 422로 막는다."""
import pytest

from tests.conftest import make_user

pytestmark = pytest.mark.asyncio

BAD = [("HEIGHT", 300), ("WEIGHT", 500), ("SBP", 1100), ("DBP", 3), ("WAIST", 500), ("HDL", 900)]


@pytest.mark.parametrize("code,value", BAD)
async def test_터무니없는_값은_422로_막는다(client, db_session, code, value):
    h = await make_user(db_session, measurements={"SMOKING": "never"})
    rec = await client.post("/v1/health/records", json={"input_type": "interim_reassessment", "examination_date": "2026-10-09"}, headers=h)
    rid = rec.json()["data"]["health_record_id"]
    r = await client.post(f"/v1/health/records/{rid}/measurements", json={"measurements": [{"metric_code": code, "value_num": value}]}, headers=h)
    assert r.status_code == 422, (code, r.status_code, r.text)
    assert r.json()["error"]["code"] == "HEALTH_VALUE_OUT_OF_RANGE"


async def test_수축기가_이완기보다_낮으면_422(client, db_session):
    h = await make_user(db_session, measurements={"SMOKING": "never"})
    rid = (await client.post("/v1/health/records", json={"input_type": "interim_reassessment", "examination_date": "2026-10-09"}, headers=h)).json()["data"]["health_record_id"]
    r = await client.post(f"/v1/health/records/{rid}/measurements", json={"measurements": [{"metric_code": "SBP", "value_num": 80}, {"metric_code": "DBP", "value_num": 120}]}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "HEALTH_VALUE_INCONSISTENT", r.text


async def test_키와_몸무게로_계산한_BMI가_비현실적이면_422(client, db_session):
    h = await make_user(db_session, measurements={"SMOKING": "never"})
    rid = (await client.post("/v1/health/records", json={"input_type": "interim_reassessment", "examination_date": "2026-10-09"}, headers=h)).json()["data"]["health_record_id"]
    r = await client.post(f"/v1/health/records/{rid}/measurements", json={"measurements": [{"metric_code": "HEIGHT", "value_num": 150}, {"metric_code": "WEIGHT", "value_num": 250}]}, headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "HEALTH_VALUE_INCONSISTENT", r.text


async def test_정상적인_값은_통과한다(client, db_session):
    h = await make_user(db_session, measurements={"SMOKING": "never"})
    rid = (await client.post("/v1/health/records", json={"input_type": "interim_reassessment", "examination_date": "2026-10-09"}, headers=h)).json()["data"]["health_record_id"]
    r = await client.post(f"/v1/health/records/{rid}/measurements", json={"measurements": [{"metric_code": "HEIGHT", "value_num": 172}, {"metric_code": "WEIGHT", "value_num": 74}, {"metric_code": "SBP", "value_num": 130}, {"metric_code": "DBP", "value_num": 85}]}, headers=h)
    assert r.status_code == 201, r.text
