from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.services import badge_service, streak_service
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
    today: date | None = None   # 서버가 정한 오늘(한국 날짜). 화면이 이 날짜로 오늘 요일을 표시한다


@router.get("/home/summary", response_model=DataResponse[HomeSummary])
async def home_summary(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await streak_service.home_summary(db, user_id, today_kst()))

class Participants(BaseModel):
    challenge_code: str
    participants: int


@router.get("/challenges/participants", response_model=DataResponse[list[Participants]])
async def participants(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await streak_service.participant_counts(db))

class Badge(BaseModel):
    code: str
    label: str
    group: str                  # streak(연속 달성) / record(완주와 기록)
    hint: str                   # 아직 못 받았을 때 보여 줄 조건
    earned: bool
    earned_on: date | None
    progress: int               # 받기까지 지금까지 한 만큼 (받았으면 목표와 같다)
    target: int                 # 받기 위한 목표 (연속 일수, 횟수 등)


class BadgeSummary(BaseModel):
    earned_count: int
    total: int
    next: Badge | None          # 다음에 받을 배지 (다 받았으면 None)
    badges: list[Badge]


@router.get("/badges", response_model=DataResponse[BadgeSummary])
async def badges(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await badge_service.my_badges(db, user_id))