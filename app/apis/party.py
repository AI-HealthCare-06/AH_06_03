from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.community import PostCreate, PostCreated, PostList
from app.schemas.party import PartyChallengeOption, PartyCreate, PartyHome, PartyInfo, PartyJoin
from app.services import community_service, party_service

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

# ---------------------------------------------------------------- 파티 피드 (파티원에게만 보이는 글)
# 글 상세·좋아요·댓글·신고는 커뮤니티 글과 같은 주소(/community/posts/...)를 쓴다. 파티 글은 그 파티원만 열 수 있다.
@router.get("/parties/me/posts", response_model=DataResponse[PostList])
async def party_posts(
    limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db),
):
    party_id = await party_service.my_party_id(db, user_id)
    return DataResponse(data=await community_service.list_posts(db, user_id, None, "latest", None, limit, offset, party_id))


@router.post("/parties/me/posts", status_code=status.HTTP_201_CREATED, response_model=DataResponse[PostCreated])
async def create_party_post(req: PostCreate, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    party_id = await party_service.my_party_id(db, user_id)
    return DataResponse(data=await community_service.create_post(db, user_id, req, party_id))
