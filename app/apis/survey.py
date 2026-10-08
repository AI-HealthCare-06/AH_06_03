"""설문 창구. API 명세서 '설문' 섹션."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.survey import SurveyResult
from app.services import survey_service
from app.schemas.survey import ResponsesRequest, SurveyInstanceDetail, SurveyInstanceResult, SurveyResult, SurveyStartRequest

router = APIRouter(tags=["survey"])

SurveyType = Literal["initial_lifestyle", "interim_lifestyle", "sodium"]


@router.get("/surveys/{survey_type}/active", response_model=DataResponse[SurveyResult])
async def get_active_survey(
    survey_type: SurveyType,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await survey_service.get_active_survey(db, survey_type))

@router.post(
    "/survey-instances",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[SurveyInstanceResult],
)
async def start_survey(
    req: SurveyStartRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(
        data=await survey_service.start_survey(db, user_id, req.survey_version_id, req.health_record_id)
    )

@router.post(
    "/survey-instances/{survey_instance_id}/responses",
    response_model=DataResponse[SurveyInstanceResult],
)
async def save_responses(
    survey_instance_id: str,
    req: ResponsesRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    items = [r.model_dump() for r in req.responses]
    return DataResponse(data=await survey_service.save_responses(db, user_id, survey_instance_id, items))

@router.post(
    "/survey-instances/{survey_instance_id}/submit",
    response_model=DataResponse[SurveyInstanceResult],
)
async def submit_survey(
    survey_instance_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await survey_service.submit_survey(db, user_id, survey_instance_id))


# 주의: /latest는 /{survey_instance_id}보다 먼저 선언해야 "latest"가 번호로 읽히지 않는다.
@router.get("/survey-instances/latest", response_model=DataResponse[SurveyInstanceDetail])
async def get_latest_instance(
    survey_type: Literal["initial_lifestyle", "interim_lifestyle", "sodium"] | None = Query(default=None, description="종류를 주면 그 종류 중 최근 것"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await survey_service.get_latest_instance_detail(db, user_id, survey_type))


@router.get("/survey-instances/{survey_instance_id}", response_model=DataResponse[SurveyInstanceDetail])
async def get_instance(
    survey_instance_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await survey_service.get_instance_detail(db, user_id, survey_instance_id))
