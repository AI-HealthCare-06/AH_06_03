"""회원·인증 창구. API 명세서 '회원 · 인증' 섹션."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import async_get_db
from app.schemas.auth import (
    LoginRequest, MeResult, ProfileUpdateRequest, RefreshRequest, SignupRequest, SignupResult, TokenResult,
)
from app.schemas.common import DataResponse
from app.services import auth_service

from app.apis.deps import get_current_user_id
from app.schemas.auth import LoginRequest, MeResult, SignupRequest, SignupResult, TokenResult

router = APIRouter(tags=["auth"])

@router.post("/auth/signup", status_code=status.HTTP_201_CREATED, response_model=DataResponse[SignupResult])
async def signup(req: SignupRequest, db: AsyncSession = Depends(async_get_db)):
    return DataResponse(
        data=await auth_service.signup(
            db, 
            req.email, 
            req.password, 
            req.birth_date,
            guardian_name=req.guardian_name,
            guardian_relation=req.guardian_relation,
            guardian_contact=req.guardian_contact,
            )
        )


@router.post("/auth/login", response_model=DataResponse[TokenResult])
async def login(req: LoginRequest, db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await auth_service.login(db, req.email, req.password))

@router.get("/users/me", response_model=DataResponse[MeResult])
async def me(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await auth_service.get_me(db, user_id))

@router.patch("/users/me", response_model=DataResponse[MeResult])
async def update_me(
    req: ProfileUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await auth_service.update_me(db, user_id, req.sex, req.birth_date))

@router.post("/auth/token/refresh", response_model=DataResponse[TokenResult])
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await auth_service.refresh(db, req.refresh_token))

@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    req: RefreshRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    await auth_service.logout(db, user_id, req.refresh_token)