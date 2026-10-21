"""전·후 비교: 모델 버전이 다르면 입력값 사진으로 지금 모델로 다시 계산하고, 비교 못 하면 이유를 내려 준다."""
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.core.security import create_access_token
from app.ml import predictor
from app.models.prediction import Prediction, PredictionJob
from app.models.user import User, UserProfile
from app.services import prediction_job_service as pjs
from app.services import prediction_service

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 10, 1, 3, 0)
SNAPSHOT = {"age": 45, "sex": "M", "sbp": 145, "dbp": 92, "total_chol": 212, "smoking": "current",
            "diabetes": False, "htn_status": "none", "height_cm": 172, "weight_kg": 78, "waist_cm": 90,
            "parent_htn": "yes", "drink_freq": "2_3_per_week", "drink_amount": "5_6"}


def r(status="completed", version="1"):
    return SimpleNamespace(status=status, model_version=version)


async def test_비교_못_하는_이유():
    assert pjs.comparison_reason(None, r()) == "missing"
    assert pjs.comparison_reason(r(), None) == "missing"
    assert pjs.comparison_reason(r(status="skipped"), r()) == "skipped"
    assert pjs.comparison_reason(r(version="0.1.1"), r(version="0.2.0")) == "model_version_changed"
    assert pjs.comparison_reason(r(), r()) is None


async def _old_prediction(client, Session, snapshot):
    """예전 버전으로 분석된 결과 하나를 만든다 (건강기록 상자는 창구로 만들고, 결과는 직접 넣는다)."""
    async with Session() as s:
        u = User(email="v@test.kr", password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        uid = u.user_id
    h = {"Authorization": f"Bearer {create_access_token(uid)}"}
    rec = (await client.post("/v1/health/records", json={"input_type": "initial", "examination_date": "2026-10-01"},
                             headers=h)).json()["data"]["health_record_id"]
    async with Session() as s:
        job = PredictionJob(user_id=uid, health_record_id=rec, request_type="initial", status="completed",
                            requested_at=NOW, completed_at=NOW, input_snapshot=snapshot)
        s.add(job)
        await s.flush()
        p = Prediction(prediction_job_id=job.prediction_job_id, user_id=uid, model_code="MODEL_A",
                       model_version="0.0.1-old", status="completed", score=0.9, risk_level="high", predicted_at=NOW)
        s.add(p)
        await s.commit()
        return p.prediction_id


async def test_버전이_다르면_입력값_사진으로_지금_모델로_다시_계산한다(client, db_session):
    pid = await _old_prediction(client, db_session, SNAPSHOT)
    async with db_session() as s:
        old = await s.get(Prediction, pid)
        now = await pjs.current_version_view(s, old)
    fresh = prediction_service.predict_dict(dict(SNAPSHOT)).model_a
    assert now.model_version == predictor.CURRENT_VERSION["MODEL_A"]
    assert (now.score, now.risk_level) == (fresh.probability, fresh.risk_level)       # 같은 입력이면 같은 결과
    async with db_session() as s:
        assert (await s.get(Prediction, pid)).score == 0.9                             # 저장된 예전 결과는 그대로


async def test_입력값_사진이_없으면_다시_계산하지_않고_이유를_알린다(client, db_session):
    pid = await _old_prediction(client, db_session, None)
    async with db_session() as s:
        old = await s.get(Prediction, pid)
        same = await pjs.current_version_view(s, old)
    assert same is old
    assert pjs.comparison_reason(same, r(version=predictor.CURRENT_VERSION["MODEL_A"])) == "model_version_changed"