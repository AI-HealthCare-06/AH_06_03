"""관리자 최소 기능 창구: 챌린지 카테고리·미션의 노출과 카테고리 순서.

관리자는 서버 설정(.env)의 ADMIN_EMAILS 목록에 있는 계정으로, 평소와 같은 로그인으로 들어온다.
목록이 비어 있으면 아무도 쓸 수 없다.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.config import settings
from app.core.db.databases import async_get_db
from app.core.errors import AppError
from app.repositories import user_repository
from app.schemas.admin import AdminCategory, AdminMission, CategoryPatch, MissionPatch
from app.schemas.common import DataResponse
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


async def require_admin(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)
) -> str:
    """관리자 목록에 있는 활성 계정이면 이메일을 돌려주고, 아니면 403."""
    user = await user_repository.get_user_by_id(db, user_id)
    if user is None or user.status != "active" or user.email.lower() not in settings.admin_email_set:
        raise AppError(403, "ADMIN_FORBIDDEN", "관리자만 사용할 수 있습니다.")
    return user.email


@router.get("/challenges", response_model=DataResponse[list[AdminCategory]])
async def list_challenges(admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await admin_service.list_catalog(db))


@router.patch("/challenge-categories/{category_id}", response_model=DataResponse[AdminCategory])
async def patch_category(
    category_id: str, req: CategoryPatch, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)
):
    return DataResponse(data=await admin_service.update_category(db, category_id, req.active, req.display_order, admin))


@router.patch("/challenges/{challenge_id}", response_model=DataResponse[AdminMission])
async def patch_mission(
    challenge_id: str, req: MissionPatch, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)
):
    return DataResponse(data=await admin_service.update_mission(db, challenge_id, req.active, admin))
