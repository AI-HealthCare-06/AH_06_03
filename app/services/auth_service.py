""" 회원가입/로그인 매니저, 판단을 한다 """
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    utcnow,
    verify_password,
)
from app.repositories import user_repository
from app.schemas.auth import SignupResult, TokenResult


MIN_AGE =14
INVALID_LOGIN = AppError(401, "AUTH_INVALID_CREDENTIALS", "이메일 또는 비밀번호가 맞지 않습니다.")

def _age_on(birth_date: date, today: date) -> int:
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


async def signup(db: AsyncSession, email: str, password: str, birth_date: date) -> SignupResult:
    today =utcnow().date()
    if birth_date>today:
        raise AppError(422, "AUTH_INVALID_BIRTH_DATE", "생년원일을 확인해 주세요. ")
    if _age_on(birth_date, today) < MIN_AGE:
        raise AppError(403, "AUTH_GUARDIAN_CONSENT_REQUIRED", "만 14세 미만은 법정대리인 동의가 필요합니다. ")

    email = email.lower()
    found = await user_repository.get_user_by_email(db, email)
    if found:
        raise AppError(409, "AUTH_EMAIL_DUPLICATED", "이미 가입된 이메일입니다.")

    try: 
        user=await user_repository.create_user_with_profile(db,email,hash_password(password),birth_date)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "AUTH_EMAIL_DUPLICATED", "이미 가입된 이메일입니다.")

    return SignupResult(user_id=user.user_id)

async def _issue_tokens(db: AsyncSession, user_id: str) -> TokenResult:
    """팔찌와 쿠폰을 발급한다. 쿠폰 기록은 DB에 남긴다."""
    now = utcnow()
    refresh_token = new_refresh_token()
    await user_repository.create_session(
        db,
        user_id=user_id,
        refresh_token_hash=hash_token(refresh_token),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        now=now,
    )
    await db.commit()
    return TokenResult(
        access_token=create_access_token(user_id),
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def login(db: AsyncSession, email: str, password: str) -> TokenResult:
    user = await user_repository.get_user_by_email(db, email.lower())
    if user is None or user.status != "active" or not verify_password(password, user.password_hash):
        raise INVALID_LOGIN
    return await _issue_tokens(db, user.user_id)
