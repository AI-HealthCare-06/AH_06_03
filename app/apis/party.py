from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.party import PartyChallengeOption, PartyCreate, PartyHome, PartyInfo, PartyJoin
from app.services import party_service

router = APIRouter(tags=["party"])


@router.get("/parties/challenges", response_model=DataResponse[list[PartyChallengeOption]])
async def challenge_options(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    """파티 챌린지 후보 (선택 미션 8개, 흡연·음주 제외)."""
    return DataResponse(data=await party_service.challenge_options(db))


@router.post("/parties", response_model=DataResponse[PartyInfo], status_code=201)
async def create(req: PartyCreate, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await party_service.create(db, user_id, req.name, req.intro, req.challenge_code))


@router.post("/parties/join", response_model=DataResponse[PartyInfo])
async def join(req: PartyJoin, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await party_service.join(db, user_id, req.invite_code))


@router.get("/parties/me", response_model=DataResponse[PartyHome])
async def home(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    """파티 현황: 파티원별 오늘 완료·N일 중 M일, 파티 연속 인증."""
    return DataResponse(data=await party_service.home(db, user_id))


@router.post("/parties/me/checkin", response_model=DataResponse[PartyHome])
async def checkin(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    """오늘 파티 챌린지 '완료' (하루 한 번). 마지막 파티원이 인증하면 모두에게 +3 파이."""
    return DataResponse(data=await party_service.checkin(db, user_id))


@router.post("/parties/me/leave", status_code=204)
async def leave(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    await party_service.leave(db, user_id)
    return Response(status_code=204)