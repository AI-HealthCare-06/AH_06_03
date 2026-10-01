"""회원·인증 창구. API 명세서 '회원 · 인증' 섹션."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import async_get_db
from app.schemas.auth import LoginRequest, SignupRequest, SignupResult, TokenResult
from app.schemas.common import DataResponse
from app.services import auth_service

router = APIRouter(tags=["auth"])

@router.post("/auth/signup", status_code=status.HTTP_201_CREATED, response_model=DataResponse[SignupResult])
async def signup(req: SignupRequest, db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await auth_service.signup(db, req.email, req.password, req.birth_date))


@router.post("/auth/login", response_model=DataResponse[TokenResult])
async def login(req: LoginRequest, db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await auth_service.login(db, req.email, req.password))