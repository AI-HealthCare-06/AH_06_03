from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.config import settings
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.push import EndpointIn, PushSettings, PushSettingsIn, SubscriptionIn, SubscriptionOut, VapidKey
from app.services import push_service

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-key", response_model=DataResponse[VapidKey])
async def vapid_public_key(user_id: str = Depends(get_current_user_id)):
    """화면이 구독할 때 쓰는 공개 키 (applicationServerKey). 비어 있으면 서버에 키가 없는 것이라 알림 켜기를 숨긴다."""
    return DataResponse(data=VapidKey(public_key=settings.VAPID_PUBLIC_KEY))


@router.put("/subscription", response_model=DataResponse[SubscriptionOut])
async def subscribe(req: SubscriptionIn, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    await push_service.subscribe(db, user_id, req.endpoint, req.keys.p256dh, req.keys.auth)
    return DataResponse(data=SubscriptionOut(endpoint=req.endpoint))


@router.delete("/subscription", status_code=204)
async def unsubscribe(req: EndpointIn, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    await push_service.unsubscribe(db, user_id, req.endpoint)
    return Response(status_code=204)


@router.get("/settings", response_model=DataResponse[PushSettings])
async def get_settings(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await push_service.get_settings(db, user_id))


@router.patch("/settings", response_model=DataResponse[PushSettings])
async def update_settings(req: PushSettingsIn, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await push_service.update_settings(db, user_id, req.model_dump()))