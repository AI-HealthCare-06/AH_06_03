"""여러 창구가 같이 쓰는 준비물: 로그인한 사용자 확인."""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError
from app.core.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    # Authorization: Bearer <팔찌> 헤더를 확인하고 회원 번호를 돌려준다.
    if credentials is None:
        raise AppError(401, "AUTH_UNAUTHORIZED", "로그인이 필요합니다.")
    user_id =decode_access_token(credentials.credentials)
    if user_id is None:
        raise AppError(401, "AUTH_TOKEN_EXPIRED", "로그인이 만료되었습니다.")
    return user_id
