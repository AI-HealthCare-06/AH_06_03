"""공통 챌린지. 이용자용(router)은 참여·인증·순위 조회, 관리자용(admin_router)은 만들기·고치기·순위 확정.

건강정보 동의와 상관없이 로그인한 회원이면 쓸 수 있다. 관리자 구분은 app/apis/admin.py의 require_admin을 그대로 쓴다.
"""
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.admin import require_admin
from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.common_challenge import (
    AdminChallengeItem, AdminChallengeList, CertifyRequest, CertifyResult, ChallengeCreate, ChallengePatch,
    CommonChallengeDetail, CommonChallengeList, FinalizeResult, JoinResult,
)
from app.services import common_challenge_service as svc

router = APIRouter(prefix="/common-challenges", tags=["common-challenges"])
admin_router = APIRouter(prefix="/admin/common-challenges", tags=["admin"])


@router.get("", response_model=DataResponse[CommonChallengeList])
async def list_challenges(
    state: Literal["active", "upcoming", "ended"] | None = None,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await svc.list_challenges(db, user_id, state))


@router.get("/{challenge_id}", response_model=DataResponse[CommonChallengeDetail])
async def challenge_detail(challenge_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await svc.detail(db, user_id, challenge_id))


@router.post("/{challenge_id}/join", status_code=status.HTTP_201_CREATED, response_model=DataResponse[JoinResult])
async def join(challenge_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await svc.join(db, user_id, challenge_id))


@router.post("/{challenge_id}/certify", status_code=status.HTTP_201_CREATED, response_model=DataResponse[CertifyResult])
async def certify(
    challenge_id: str, req: CertifyRequest | None = None,
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await svc.certify(db, user_id, challenge_id, req or CertifyRequest()))


@admin_router.get("", response_model=DataResponse[AdminChallengeList])
async def admin_list(admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await svc.admin_list(db, admin))


@admin_router.post("", status_code=status.HTTP_201_CREATED, response_model=DataResponse[AdminChallengeItem])
async def admin_create(req: ChallengeCreate, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await svc.admin_create(db, admin, req))


@admin_router.patch("/{challenge_id}", response_model=DataResponse[AdminChallengeItem])
async def admin_patch(
    challenge_id: str, req: ChallengePatch, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)
):
    return DataResponse(data=await svc.admin_patch(db, admin, challenge_id, req))


@admin_router.delete("/{challenge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete(challenge_id: str, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    await svc.admin_delete(db, admin, challenge_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.post("/{challenge_id}/finalize", response_model=DataResponse[FinalizeResult])
async def admin_finalize(challenge_id: str, admin: str = Depends(require_admin), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await svc.admin_finalize(db, admin, challenge_id))
