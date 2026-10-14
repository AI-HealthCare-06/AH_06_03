"""서비스 안 공지 창구.

이용자용(public_router)은 로그인 없이 지금 게시 중인 공지만 보여 주고, 관리자용(admin_router)은 목록, 작성, 수정(내리기 포함)을 한다.
관리자 구분은 app/apis/admin.py의 require_admin을 그대로 쓴다.
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.admin import require_admin
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.notice import NoticeAdmin, NoticeCreate, NoticePatch, NoticePublic
from app.services import notice_service

public_router = APIRouter(prefix="/notices", tags=["notices"])
admin_router = APIRouter(prefix="/admin/notices", tags=["admin"])


@public_router.get("", response_model=DataResponse[list[NoticePublic]])
async def active_notices(db: AsyncSession = Depends(async_get_db)):
    """지금 게시 중인 공지 (로그인 없이, 최신순)."""
    return DataResponse(data=await notice_service.list_active(db))


@admin_router.get("", response_model=DataResponse[list[NoticeAdmin]])
async def admin_notices(
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await notice_service.admin_list(db, limit, offset))


@admin_router.post("", status_code=status.HTTP_201_CREATED, response_model=DataResponse[NoticeAdmin])
async def create_notice(req: NoticeCreate, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await notice_service.create(db, admin, req))


@admin_router.patch("/{notice_id}", response_model=DataResponse[NoticeAdmin])
async def update_notice(
    notice_id: str, req: NoticePatch, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await notice_service.update(db, admin, notice_id, req))
