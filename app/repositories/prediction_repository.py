"""예측 결과 창고 담당. DB에 넣고 꺼내는 일만 한다."""
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import Prediction, PredictionFactor, PredictionJob


async def create_job(
    db: AsyncSession, user_id: str, health_record_id: str, survey_instance_id: str | None,
    request_type: str, now: datetime,
) -> PredictionJob:
    """🎫 번호표를 만든다."""
    job = PredictionJob(
        user_id=user_id,
        health_record_id=health_record_id,
        survey_instance_id=survey_instance_id,
        request_type=request_type,
        requested_at=now,
    )
    db.add(job)
    await db.flush()
    return job


async def save_result(
    db: AsyncSession, prediction_job_id: str, user_id: str, result: dict, now: datetime
) -> Prediction:
    """📊 모델 결과 한 줄 + 🔹 요인 여러 줄을 넣는다. result는 모델이 돌려준 모양 그대로."""
    p = Prediction(
        prediction_job_id=prediction_job_id,
        user_id=user_id,
        model_code=result["model_code"],
        model_version=result.get("model_version"),
        status=result["status"],
        skip_reason=result.get("skip_reason"),
        score=result.get("probability"),
        risk_level=result.get("risk_level"),
        vascular_age=result.get("vascular_age"),
        missing_features=result.get("missing_features") or None,
        predicted_at=now,
    )
    db.add(p)
    await db.flush()

    for f in result.get("factors", []):
        db.add(PredictionFactor(
            prediction_id=p.prediction_id,
            factor_code=f["code"],
            label=f["label"],
            value_label=f.get("value_label"),
            importance=f["contribution"],
            direction=f["direction"],
            modifiable=f["modifiable"],
            direction_matches_expectation=f["direction_matches_expectation"],
            display_rank=f["display_rank"],
        ))
    return p