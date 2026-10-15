"""여러 창구가 같이 쓰는 준비물: 로그인한 사용자 확인."""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import async_get_db
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.repositories import user_repository
from app.services import suspension

bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(async_get_db),
) -> str:
    """Authorization: Bearer <팔찌> 헤더를 확인하고 회원 번호를 돌려준다.
    팔찌 도장이 맞아도, 그 사이 탈퇴한 회원이면 막는다 (팔찌는 30분 동안 살아 있어서)."""
    if credentials is None:
        raise AppError(401, "AUTH_UNAUTHORIZED", "로그인이 필요합니다.")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise AppError(401, "AUTH_TOKEN_EXPIRED", "로그인이 만료되었습니다.")
    user = await user_repository.get_user_by_id(db, user_id)
    if user is None or user.status == "deleted":
        raise AppError(401, "AUTH_UNAUTHORIZED", "다시 로그인해 주세요.")
    suspension.check(user)
    return user_id