"""관리자 최소 기능 창구: 챌린지 카테고리·미션의 노출과 카테고리 순서.

관리자는 서버 설정(.env)의 ADMIN_EMAILS 목록에 있는 계정으로, 평소와 같은 로그인으로 들어온다.
목록이 비어 있으면 아무도 쓸 수 없다.
"""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.config import settings
from app.core.db.databases import async_get_db
from app.core.errors import AppError
from app.repositories import user_repository
from app.schemas.admin import (
    AdminCategory, AdminMission, AdminUserDetail, AdminUserEmail, AdminUserList, AuditLogItem, CategoryPatch, ChallengeStats, MissionPatch,
    PurgeRequest, PurgeResult,
)
from app.schemas.common import DataResponse
from app.schemas.admin import SuspendRequest
from app.schemas.inquiry import AdminGuestDetail, AdminGuestList, AdminInquiryDetail, AdminInquiryList, AnswerRequest
from app.services import admin_service, admin_users_service, audit_service, guest_inquiry_service, inquiry_service

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
    data = await admin_service.list_catalog(db)
    await audit_service.record(db, admin, "catalog_view", dedupe_seconds=audit_service.VIEW_DEDUPE_SECONDS)
    await db.commit()
    return DataResponse(data=data)


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


@router.get("/users", response_model=DataResponse[AdminUserList])
async def list_users(
    q: str | None = None, stage: str | None = None, consent: str | None = None, status: str | None = None,
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await admin_users_service.list_users(db, admin, q, stage, consent, status, limit, offset))


@router.get("/users/{user_id}", response_model=DataResponse[AdminUserDetail])
async def user_detail(user_id: str, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await admin_users_service.user_detail(db, admin, user_id))


@router.get("/users/{user_id}/email", response_model=DataResponse[AdminUserEmail])
async def user_email(user_id: str, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    """가린 이메일을 풀어 전체를 보여 준다. 볼 때마다 관리자 기록(user_email_view)에 남는다."""
    return DataResponse(data=AdminUserEmail(email=await admin_users_service.reveal_email(db, admin, user_id)))


@router.post("/purge", response_model=DataResponse[PurgeResult])
async def purge(req: PurgeRequest, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await admin_users_service.purge(db, admin, req.patterns, req.apply, req.confirm_count))


@router.get("/stats/challenges", response_model=DataResponse[ChallengeStats])
async def challenge_stats(admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    data = await admin_service.challenge_stats(db)
    await audit_service.record(db, admin, "stats_view", dedupe_seconds=audit_service.VIEW_DEDUPE_SECONDS)
    await db.commit()
    return DataResponse(data=data)


@router.get("/audit-logs", response_model=DataResponse[list[AuditLogItem]])
async def audit_logs(
    limit: int = Query(100, ge=1, le=500), admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)
):
    """관리자 행위 기록 (최신순). 이 화면을 본 것도 기록에 남는다."""
    data = await audit_service.list_logs(db, limit)
    await audit_service.record(db, admin, "audit_view", dedupe_seconds=audit_service.VIEW_DEDUPE_SECONDS)
    await db.commit()
    return DataResponse(data=data)


@router.get("/inquiries", response_model=DataResponse[AdminInquiryList])
async def inquiries(
    status: str | None = Query(None, pattern="^(open|answered)$"), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await inquiry_service.admin_list(db, admin, status, limit, offset))


@router.get("/inquiries/{inquiry_id}", response_model=DataResponse[AdminInquiryDetail])
async def inquiry_detail(inquiry_id: str, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await inquiry_service.admin_detail(db, admin, inquiry_id))


@router.put("/inquiries/{inquiry_id}/answer", response_model=DataResponse[AdminInquiryDetail])
async def answer_inquiry(inquiry_id: str, req: AnswerRequest, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await inquiry_service.admin_answer(db, admin, inquiry_id, req.answer))


@router.delete("/inquiries/{inquiry_id}", status_code=204)
async def delete_inquiry(inquiry_id: str, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    await inquiry_service.admin_delete(db, admin, inquiry_id)
    return Response(status_code=204)


@router.delete("/guest-inquiries/{inquiry_id}", status_code=204)
async def delete_guest_inquiry(inquiry_id: str, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    await guest_inquiry_service.admin_delete(db, admin, inquiry_id)
    return Response(status_code=204)


@router.get("/guest-inquiries", response_model=DataResponse[AdminGuestList])
async def guest_inquiries(
    status: str | None = Query(None, pattern="^(open|answered)$"), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await guest_inquiry_service.admin_list(db, admin, status, limit, offset))


@router.get("/guest-inquiries/{inquiry_id}", response_model=DataResponse[AdminGuestDetail])
async def guest_inquiry_detail(inquiry_id: str, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await guest_inquiry_service.admin_detail(db, admin, inquiry_id))


@router.put("/guest-inquiries/{inquiry_id}/answer", response_model=DataResponse[AdminGuestDetail])
async def answer_guest_inquiry(inquiry_id: str, req: AnswerRequest, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await guest_inquiry_service.admin_answer(db, admin, inquiry_id, req.answer))


# ---------------------------------------------------------------- 회원 조치 (신고 처리 등에서)
@router.post("/users/{user_id}/suspend", status_code=204)
async def suspend_user(user_id: str, req: SuspendRequest, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    """이용 정지. days를 비우면 무기한. 관리자 계정은 정지할 수 없다."""
    await admin_users_service.suspend(db, admin, user_id, req.days)
    return Response(status_code=204)


@router.post("/users/{user_id}/unsuspend", status_code=204)
async def unsuspend_user(user_id: str, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    await admin_users_service.unsuspend(db, admin, user_id)
    return Response(status_code=204)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: str, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    """회원 탈퇴 처리(모든 데이터 삭제, 되돌릴 수 없음). 관리자 계정은 지울 수 없다."""
    await admin_users_service.delete_user(db, admin, user_id)
    return Response(status_code=204)
