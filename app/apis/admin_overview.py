"""관리자 운영 현황 창구: 진행 현황, 동의·삭제 현황, 서비스 상태, 집계 CSV 내려받기.

관리자 구분은 app/apis/admin.py의 require_admin을 그대로 쓰고, 열람과 내려받기는 관리자 행위 기록에 남긴다.
"""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.admin import require_admin
from app.core.db.databases import async_get_db
from app.core.security import utcnow
from app.schemas.admin_overview import Overview
from app.schemas.common import DataResponse
from app.services import admin_overview_service, audit_service

router = APIRouter(prefix="/admin/overview", tags=["admin"])


@router.get("", response_model=DataResponse[Overview])
async def overview(
    days: int = Query(14, ge=1, le=90, description="날짜별 활동을 보여 줄 최근 일수"),
    admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db),
):
    data = await admin_overview_service.build_overview(db, days)
    await audit_service.record(db, admin, "overview_view", dedupe_seconds=audit_service.VIEW_DEDUPE_SECONDS)
    await db.commit()
    return DataResponse(data=data)


@router.get("/export.csv")
async def export_csv(admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    content = await admin_overview_service.export_csv(db)
    await audit_service.record(db, admin, "overview_csv_export", detail="집계 CSV (사용자별 행 없음)")
    await db.commit()
    filename = f"paeon-overview-{utcnow():%Y%m%d}.csv"
    return Response(
        content=("\ufeff" + content).encode("utf-8"),     # 엑셀에서 한글이 깨지지 않게 BOM을 붙인다
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )
