"""예측 정식 창구. API 명세서 '예측 실행 · 결과' 섹션."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.prediction import PredictionJobRequest, PredictionJobResult, PredictionSummary, ReassessmentCompareResult
from app.services import prediction_job_service

router = APIRouter(tags=["prediction-job"])


@router.post(
    "/predictions/jobs",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[PredictionJobResult],
)
async def create_job(
    req: PredictionJobRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(
        data=await prediction_job_service.create_job(
            db, user_id, req.health_record_id, req.survey_instance_id, req.request_type
        )
    )

@router.get("/predictions/latest", response_model=DataResponse[PredictionJobResult])
async def get_latest(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await prediction_job_service.get_latest(db, user_id))

@router.get("/predictions", response_model=DataResponse[list[PredictionSummary]])
async def list_history(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await prediction_job_service.list_history(db, user_id))

@router.get("/predictions/{prediction_job_id}", response_model=DataResponse[PredictionJobResult])
async def get_detail(
    prediction_job_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await prediction_job_service.get_detail(db, user_id, prediction_job_id))

@router.get("/reassessments/latest", response_model=DataResponse[ReassessmentCompareResult])
async def compare_latest(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await prediction_job_service.compare_latest(db, user_id))