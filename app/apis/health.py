"""건강기록 창구. API 명세서 '건강정보 입력' 섹션."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.health import (
    HealthRecordCreateRequest,
    HealthRecordDetail,
    HealthRecordResult,
    MeasurementResult,
    MeasurementsCreateRequest,
)
from app.services import health_service

router = APIRouter(tags=["health"])


@router.post("/health/records", status_code=status.HTTP_201_CREATED, response_model=DataResponse[HealthRecordResult])
async def create_record(
    req: HealthRecordCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(
        data=await health_service.create_record(db, user_id, req.input_type, req.examination_date)
    )


@router.post(
    "/health/records/{health_record_id}/measurements",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[list[MeasurementResult]],
)
async def add_measurements(
    health_record_id: str,
    req: MeasurementsCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    items = [m.model_dump() for m in req.measurements]
    return DataResponse(data=await health_service.add_measurements(db, user_id, health_record_id, items))

@router.get("/health/records", response_model=DataResponse[list[HealthRecordResult]])
async def list_records(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await health_service.list_records(db, user_id))


# 주의: /latest는 /{health_record_id}보다 먼저 선언해야 "latest"가 번호로 읽히지 않는다.
@router.get("/health/records/latest", response_model=DataResponse[HealthRecordDetail])
async def get_latest_record(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await health_service.get_latest_record_detail(db, user_id))


@router.get("/health/records/{health_record_id}", response_model=DataResponse[HealthRecordDetail])
async def get_record(
    health_record_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await health_service.get_record_detail(db, user_id, health_record_id))
