from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.character import BuyRequest, CharacterSave, CharacterView, ItemsResult
from app.schemas.common import DataResponse
from app.services import character_service

router = APIRouter(tags=["character"])


@router.get("/characters/items", response_model=DataResponse[ItemsResult])
async def list_items(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    """아이템 전체(가격·보유 여부) + 내 파이 잔액."""
    return DataResponse(data=await character_service.list_items(db, user_id))


@router.post("/characters/items/buy", response_model=DataResponse[ItemsResult])
async def buy(req: BuyRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    """아이템 구매. 보유 기록과 파이 차감이 함께 저장된다."""
    return DataResponse(data=await character_service.buy(db, user_id, req.item_key))


@router.get("/characters/me", response_model=DataResponse[CharacterView])
async def get_me(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await character_service.get_me(db, user_id))


@router.put("/characters/me", response_model=DataResponse[CharacterView])
async def save_me(req: CharacterSave, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    """조합 저장. 각 칸은 무료이거나 산 아이템이어야 한다."""
    return DataResponse(data=await character_service.save_me(db, user_id, req.model_dump()))


@router.get("/characters/by-nickname/{nickname}", response_model=DataResponse[CharacterView])
async def by_nickname(nickname: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    """닉네임으로 다른 사람의 캐릭터 보기 (프로필 화면용)."""
    return DataResponse(data=await character_service.by_nickname(db, nickname))