"""회원 탈퇴 창구 (API 명세서 '동의·탈퇴')."""
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.services import account_service
from app.services.account_service import DeletionResult

router = APIRouter(tags=["account"])


class DeletionRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=72, description="재인증용 현재 비밀번호")


@router.post("/users/me/deletion-requests", status_code=status.HTTP_201_CREATED, response_model=DataResponse[DeletionResult])
async def request_deletion(
    req: DeletionRequestBody,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    """회원 탈퇴. 비밀번호로 재인증한 뒤 내 건강정보·설문·예측·캘린더 등을 모두 지우고 계정을 익명화한다."""
    return DataResponse(data=await account_service.request_deletion(db, user_id, req.password))


@router.get("/users/me/deletion-requests/{deletion_request_id}", response_model=DataResponse[DeletionResult])
async def get_deletion(
    deletion_request_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await account_service.get_deletion(db, user_id, deletion_request_id))


@router.get("/users/me/data-export")
async def export_data(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    """내 데이터 내려받기 (JSON 파일). 비밀번호·토큰 해시는 빠진다."""
    return JSONResponse(
        await account_service.export_my_data(db, user_id),
        headers={"Content-Disposition": 'attachment; filename="paeon-my-data.json"'},
    )
