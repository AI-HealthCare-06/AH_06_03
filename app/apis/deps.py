"""여러 창구가 같이 쓰는 준비물: 로그인한 사용자 확인."""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import async_get_db
from app.core.errors import AppError
from app.core.security import decode_access_claims
from app.models.user import UserSession
from app.repositories import user_repository
from app.services import suspension

bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(async_get_db),
) -> str:
    """Authorization: Bearer <팔찌> 헤더를 확인하고 회원 번호를 돌려준다.
    팔찌 도장이 맞아도, 그 사이 탈퇴한 회원이면 막는다 (팔찌는 30분 동안 살아 있어서).
    팔찌에 로그인 번호(sid)가 있으면 그 로그인이 끊겼는지도 본다 (다른 기기에서 로그인, 로그아웃, 이용 정지).
    sid가 없는 팔찌는 이 기능 전에 발급된 것(최대 30분)과 시험용뿐이라 예전처럼 통과시킨다."""
    if credentials is None:
        raise AppError(401, "AUTH_UNAUTHORIZED", "로그인이 필요합니다.")
    claims = decode_access_claims(credentials.credentials)
    if claims is None:
        raise AppError(401, "AUTH_TOKEN_EXPIRED", "로그인이 만료되었습니다.")
    user_id = claims["sub"]
    user = await user_repository.get_user_by_id(db, user_id)
    if user is None or user.status == "deleted":
        raise AppError(401, "AUTH_UNAUTHORIZED", "다시 로그인해 주세요.")
    suspension.check(user)
    sid = claims.get("sid")
    if sid is not None:
        session = await db.get(UserSession, sid)
        if session is None or session.user_id != user_id or session.revoked_at is not None:
            raise AppError(401, "AUTH_SESSION_ENDED", "다른 기기에서 로그인해 이 기기는 로그아웃됐어요. 다시 로그인해 주세요.")
    return user_id