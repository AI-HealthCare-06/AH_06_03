"""파이(포인트). 건강정보 동의와 상관없이 로그인한 회원이면 쓸 수 있다."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.pie import PieHistory, PieSummary, ThanksStatus
from app.services import pie_service

router = APIRouter(tags=["pie"])


@router.get("/pie", response_model=DataResponse[PieSummary])
async def my_pie(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await pie_service.summary(db, user_id))


@router.get("/pie/history", response_model=DataResponse[PieHistory])
async def my_pie_history(
    limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await pie_service.history(db, user_id, limit, offset))


@router.get("/pie/thanks", response_model=DataResponse[ThanksStatus])
async def thanks_status(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await pie_service.thanks_status(db, user_id))


@router.post("/pie/thanks", response_model=DataResponse[ThanksStatus])
async def claim_thanks(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await pie_service.claim_thanks(db, user_id))
