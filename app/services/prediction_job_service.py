"""예측 정식 방식 매니저. 저장된 건강기록·설문을 꺼내 모델에 넣고 결과를 저장한다."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.repositories import health_repository, prediction_repository, user_repository
from app.schemas.prediction import PredictionJobResult,Factor,ModelResult
from app.services import prediction_service
from app.services.model_input import build_model_input


async def create_job(
    db: AsyncSession, user_id: str, health_record_id: str, survey_instance_id: str | None, request_type: str
) -> PredictionJobResult:
    # 1. 내 상자인가?
    record = await health_repository.get_health_record(db, health_record_id)
    if record is None or record.user_id != user_id:
        raise AppError(404, "HEALTH_RECORD_NOT_FOUND", "건강기록을 찾을 수 없습니다.")

    # 2. 성별이 들어 있나?
    profile = await user_repository.get_profile(db, user_id)
    if profile is None or profile.sex is None:
        raise AppError(422, "PREDICTION_SEX_REQUIRED", "성별을 먼저 입력해 주세요.")


    # 4. 꺼내기 + 번역하기
        # 4. 꺼내기 + 번역하기 (건강정보만)
    measurements = await health_repository.get_measurements(db, record.health_record_id)
    items = [{"metric_code": m.metric_code, "value_num": m.value_num, "value_code": m.value_code} for m in measurements]
    user_input = build_model_input(profile.sex, profile.birth_date, record.examination_date, items)

    # 5. 번호표 만들기
    now = utcnow()
    job = await prediction_repository.create_job(
        db, user_id, record.health_record_id, None, request_type, now
    )
    job.input_snapshot = user_input

    # 6. 모델 A·B 실행
    result = prediction_service.predict_dict(user_input)

    # 7. 결과 저장하기 (모델마다 한 줄씩)
    for model_result in (result.model_a, result.model_b):
        await prediction_repository.save_result(db, job.prediction_job_id, user_id, model_result.model_dump(), now)

    # 8. 번호표를 "완료"로 고치고 진짜 저장
    job.status = "completed"
    job.completed_at = now
    await db.commit()

    return PredictionJobResult(
        prediction_job_id=job.prediction_job_id,
        status=job.status,
        model_a=result.model_a,
        model_b=result.model_b,
    )

def _to_model_result(p, factors: list) -> ModelResult:
    """DB 줄 → 모델 결과 모양으로 거꾸로 번역."""
    fs = [
        Factor(
            code=f.factor_code,
            label=f.label,
            value_label=f.value_label,
            contribution=f.importance,
            direction=f.direction,
            modifiable=f.modifiable,
            direction_matches_expectation=f.direction_matches_expectation,
            display_rank=f.display_rank,
        )
        for f in factors
    ]
    risk_up = [f for f in fs if f.direction == "risk_increase"]
    return ModelResult(
        model_code=p.model_code,
        model_version=p.model_version,
        status=p.status,
        skip_reason=p.skip_reason,
        probability=p.score,
        risk_level=p.risk_level,
        vascular_age=p.vascular_age,
        factors=fs,
        top_risk_factor=risk_up[0] if risk_up else None,
        top_modifiable_factor=next((f for f in risk_up if f.modifiable), None),
        missing_features=p.missing_features or [],
    )


async def get_latest(db: AsyncSession, user_id: str) -> PredictionJobResult:
    """내 최근 예측 결과 다시 보기."""
    job = await prediction_repository.get_latest_completed_job(db, user_id)
    if job is None:
        raise AppError(404, "PREDICTION_NOT_FOUND", "아직 예측 결과가 없습니다.")

    predictions = await prediction_repository.get_predictions(db, job.prediction_job_id)
    factors = await prediction_repository.get_factors(db, [p.prediction_id for p in predictions])

    baskets = {}
    for f in factors:
        baskets.setdefault(f.prediction_id, []).append(f)

    results = {p.model_code: _to_model_result(p, baskets.get(p.prediction_id, [])) for p in predictions}
    return PredictionJobResult(
        prediction_job_id=job.prediction_job_id,
        status=job.status,
        model_a=results["MODEL_A"],
        model_b=results["MODEL_B"],
    )