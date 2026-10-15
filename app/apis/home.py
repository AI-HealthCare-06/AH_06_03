from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.services import streak_service
from app.services.challenge_service import today_kst

router = APIRouter(tags=["home"])


class WeekDay(BaseModel):
    date: date
    done: bool


class HomeSummary(BaseModel):
    streak: int                 # 연속 달성 N일째
    week: list[WeekDay]         # 이번 주 월~일
    today_done: int             # 오늘 구운 파이 조각
    today_total: int            # 오늘 파이 전체 조각 (진행 중인 미션 수, 사이클이 없으면 0)


@router.get("/home/summary", response_model=DataResponse[HomeSummary])
async def home_summary(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await streak_service.home_summary(db, user_id, today_kst()))