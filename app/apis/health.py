"""건강기록 창구. API 명세서 '건강정보 입력' 섹션."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.health import (
    HealthRecordCreateRequest,
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