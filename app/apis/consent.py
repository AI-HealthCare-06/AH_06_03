"""동의·철회 창구 (API 명세서 '동의·탈퇴')."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.core.errors import AppError
from app.schemas.common import DataResponse
from app.services import consent_service
from app.services.consent_service import ConsentResult, PolicyResult

router = APIRouter(tags=["consent"])


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str


@router.get("/consent-policies/active", response_model=DataResponse[list[PolicyResult]])
async def active_policies(db: AsyncSession = Depends(async_get_db)):
    """지금 유효한 약관 (종류별 최신 버전). 로그인 없이 볼 수 있다."""
    return DataResponse(data=await consent_service.list_active_policies(db))


@router.get("/users/me/consents", response_model=DataResponse[list[ConsentResult]])
async def my_consents(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await consent_service.list_my_consents(db, user_id))


@router.post("/users/me/consents", response_model=DataResponse[ConsentResult])
async def agree(req: ConsentRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await consent_service.agree(db, user_id, req.policy_id))


@router.delete("/users/me/consents/{policy_id}", response_model=DataResponse[ConsentResult])
async def withdraw(policy_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    """동의 철회. 계정은 유지된다. 건강정보 동의를 철회하면 건강정보 API가 403이 된다."""
    return DataResponse(data=await consent_service.withdraw(db, user_id, policy_id))


async def require_health_consent(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)) -> str:
    """건강정보 API 앞에 거는 확인: 건강정보 동의를 철회했으면 403."""
    if await consent_service.health_consent_withdrawn(db, user_id):
        raise AppError(403, "CONSENT_WITHDRAWN", "건강정보 처리 동의를 철회하셨어요. 마이페이지에서 다시 동의하면 이용할 수 있어요.")
    return user_id
