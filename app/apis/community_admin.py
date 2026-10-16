"""커뮤니티 신고 처리 (관리자). 관리자 구분은 app/apis/admin.py의 require_admin을 그대로 쓴다."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.admin import require_admin
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.community import (
    AdminPostActionRequest, AdminPostActionResult, AdminPostList, AdminReportList, ReportActionRequest, ReportActionResult,
)
from app.services import report_service

admin_router = APIRouter(prefix="/admin/reports", tags=["admin"])


@admin_router.get("", response_model=DataResponse[AdminReportList])
async def reports(
    status: Literal["pending", "done"] | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await report_service.admin_list(db, admin, status, limit, offset))


@admin_router.post("/{target_type}/{target_id}/action", response_model=DataResponse[ReportActionResult])
async def report_action(
    target_type: str, target_id: str, req: ReportActionRequest,
    admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await report_service.act(db, admin, target_type, target_id, req.action))

# ---------------------------------------------------------------- 관리자 글 관리 (신고 없이)
posts_router = APIRouter(prefix="/admin/community", tags=["admin"])


@posts_router.get("/posts", response_model=DataResponse[AdminPostList])
async def posts(
    q: str | None = Query(None, max_length=50, description="제목·본문 검색어"),
    status: Literal["visible", "hidden", "deleted"] | None = None,
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db),
):
    """전체 커뮤니티 글 (최신순, 파티 글 제외). 연 것은 관리자 기록에 남는다."""
    return DataResponse(data=await report_service.admin_posts(db, admin, q, status, limit, offset))


@posts_router.post("/posts/{post_id}/action", response_model=DataResponse[AdminPostActionResult])
async def post_action(
    post_id: str, req: AdminPostActionRequest,
    admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db),
):
    """신고 없이 숨김(hide) / 삭제(delete) / 다시 보이기(restore)."""
    return DataResponse(data=await report_service.moderate_post(db, admin, post_id, req.action))
