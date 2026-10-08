"""예측 정식 방식 매니저. 저장된 건강기록·설문을 꺼내 모델에 넣고 결과를 저장한다."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.repositories import health_repository, prediction_repository, user_repository
from app.schemas.prediction import PredictionJobResult,Factor,ModelResult, ModelSummary, PredictionJobResult, PredictionSummary
from app.services import prediction_service
from app.services.model_input import build_model_input

# 4주 재평가에서 다시 받지 않고 직전 값을 쓰는 지표 (ERD v8 health_measurements Note, 명세 §6.1)
CARRY_FORWARD = ["HEIGHT", "TOTAL_CHOL", "HDL", "FASTING_GLUCOSE", "DIABETES", "HTN_STATUS", "PARENT_HTN"]


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

    # 4. 꺼내기 + 번역하기 (건강정보만)
    if request_type == "interim":
        await _carry_forward(db, user_id, record)  # 4주 상자에 없는 이월 지표를 채워 넣기
        await db.flush()

    measurements = await health_repository.get_measurements(db, record.health_record_id)
    items = [{"metric_code": m.metric_code, "value_num": m.value_num, "value_code": m.value_code} for m in measurements]
    user_input = build_model_input(profile.sex, profile.birth_date, record.examination_date, items)

    if request_type == "interim":
        first = await prediction_repository.get_first_snapshot(db, user_id)
        if first and "age" in first:
            user_input["age"] = first["age"]  # 나이는 처음 예측 값 유지 (명세 §6.1)


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

async def _carry_forward(db: AsyncSession, user_id: str, record) -> None:
    """4주 상자에 없는 이월 지표를, 내 예전 상자에서 가장 최근 값으로 복사해 넣는다."""
    existing = await health_repository.get_measurements(db, record.health_record_id)
    have = {m.metric_code for m in existing}
    missing = [code for code in CARRY_FORWARD if code not in have]
    if not missing:
        return

    previous = await health_repository.get_previous_measurements(db, user_id, record.health_record_id, missing)
    picked = {}
    for m in previous:
        if m.metric_code not in picked:  # 최근 검진부터 나오니, 처음 나온 게 가장 최근 값
            picked[m.metric_code] = m

    items = [
        {
            "metric_code": m.metric_code,
            "value_num": m.value_num,
            "value_code": m.value_code,
            "unit": m.unit,
            "input_method": "carried_forward",
            "source_measurement_id": m.measurement_id,
        }
        for m in picked.values()
    ]
    if items:
        await health_repository.create_measurements(
            db, record.health_record_id, record.examination_date, items, utcnow()
        )

def _summary(p) -> ModelSummary | None:
    """DB 결과 한 줄 → 목록용 요약 (확률·요인은 빼고)."""
    if p is None:
        return None
    return ModelSummary(
        status=p.status,
        model_version=p.model_version,
        risk_level=p.risk_level,
        vascular_age=p.vascular_age,
        skip_reason=p.skip_reason,
    )


async def list_history(db: AsyncSession, user_id: str) -> list[PredictionSummary]:
    """내 예측 이력 (최근 것부터, 최대 20개)."""
    jobs = await prediction_repository.list_completed_jobs(db, user_id)
    job_ids = [j.prediction_job_id for j in jobs]
    predictions = await prediction_repository.get_predictions_for_jobs(db, job_ids)
    records = await health_repository.get_records_by_ids(db, [j.health_record_id for j in jobs])
    exam_dates = {r.health_record_id: r.examination_date for r in records}

    # 🧺 결과를 번호표별 바구니에: {번호표: {"MODEL_A": 결과, "MODEL_B": 결과}}
    baskets = {}
    for p in predictions:
        baskets.setdefault(p.prediction_job_id, {})[p.model_code] = p

    return [
        PredictionSummary(
            prediction_job_id=j.prediction_job_id,
            request_type=j.request_type,
            examination_date=exam_dates[j.health_record_id],
            completed_at=j.completed_at,
            model_a=_summary(baskets.get(j.prediction_job_id, {}).get("MODEL_A")),
            model_b=_summary(baskets.get(j.prediction_job_id, {}).get("MODEL_B")),
        )
        for j in jobs
    ]