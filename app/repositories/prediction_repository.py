"""예측 결과 창고 담당. DB에 넣고 꺼내는 일만 한다."""
from datetime import datetime
from sqlalchemy import select
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

async def get_latest_completed_job(db: AsyncSession, user_id: str) -> PredictionJob | None:
    """🎫 이 사람의 가장 최근 완료된 번호표."""
    result = await db.execute(
        select(PredictionJob)
        .where(PredictionJob.user_id == user_id)
        .where(PredictionJob.status == "completed")
        .order_by(PredictionJob.completed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_predictions(db: AsyncSession, prediction_job_id: str) -> list[Prediction]:
    """📊 그 번호표의 모델별 결과들."""
    result = await db.execute(select(Prediction).where(Prediction.prediction_job_id == prediction_job_id))
    return list(result.scalars().all())


async def get_factors(db: AsyncSession, prediction_ids: list[str]) -> list[PredictionFactor]:
    """🔹 그 결과들의 요인을 한 번에 (화면 순서대로)."""
    if not prediction_ids:
        return []
    result = await db.execute(
        select(PredictionFactor)
        .where(PredictionFactor.prediction_id.in_(prediction_ids))
        .order_by(PredictionFactor.display_rank)
    )
    return list(result.scalars().all())

async def is_record_used(db: AsyncSession, health_record_id: str) -> bool:
    """🔒 이 상자로 예측한 번호표가 하나라도 있나?"""
    result = await db.execute(
        select(PredictionJob.prediction_job_id)
        .where(PredictionJob.health_record_id == health_record_id)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None

async def get_first_snapshot(db: AsyncSession, user_id: str) -> dict | None:
    """📸 이 사람이 처음 예측할 때 찍어 둔 입력값 (4주 재평가 나이 고정용)."""
    result = await db.execute(
        select(PredictionJob.input_snapshot)
        .where(PredictionJob.user_id == user_id)
        .where(PredictionJob.input_snapshot.is_not(None))
        .order_by(PredictionJob.requested_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()

async def list_completed_jobs(db: AsyncSession, user_id: str, limit: int = 20) -> list[PredictionJob]:
    """🎫 내 완료된 번호표들, 최근 것부터."""
    result = await db.execute(
        select(PredictionJob)
        .where(PredictionJob.user_id == user_id)
        .where(PredictionJob.status == "completed")
        .order_by(PredictionJob.completed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_predictions_for_jobs(db: AsyncSession, job_ids: list[str]) -> list[Prediction]:
    """📊 여러 번호표의 모델별 결과를 한 번에."""
    if not job_ids:
        return []
    result = await db.execute(
        select(Prediction).where(Prediction.prediction_job_id.in_(job_ids))
    )
    return list(result.scalars().all())

async def get_job(db: AsyncSession, prediction_job_id: str) -> PredictionJob | None:
    """🎫 번호표 번호로 번호표를 찾는다."""
    return await db.get(PredictionJob, prediction_job_id)