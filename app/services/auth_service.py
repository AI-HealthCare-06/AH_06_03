""" 회원가입/로그인 매니저, 판단을 한다 """
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    encrypt_text,
    hash_password,
    hash_token,
    new_refresh_token,
    utcnow,
    verify_password,
)
from app.repositories import user_repository
from app.schemas.auth import SignupResult, TokenResult, MeResult


MIN_AGE =19
INVALID_LOGIN = AppError(401, "AUTH_INVALID_CREDENTIALS", "이메일 또는 비밀번호가 맞지 않습니다.")
GUARDIAN_PURGE_DAYS = 5  # 미확인 법정대리인 정보 파기 기한 (REQ-CONSENT-003)


def _age_on(birth_date: date, today: date) -> int:
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

async def signup(
    db: AsyncSession,
    email: str,
    password: str,
    birth_date: date,
    guardian_name: str | None = None,
    guardian_relation: str | None = None,
    guardian_contact: str | None = None,
) -> SignupResult:
    today = utcnow().date()
    if birth_date > today:
        raise AppError(422, "AUTH_INVALID_BIRTH_DATE", "생년월일을 확인해 주세요.")
    if _age_on(birth_date, today) < MIN_AGE:
        raise AppError(403, "AUTH_ADULT_ONLY", "만 19세 이상만 가입할 수 있습니다.")

    email = email.lower()
    if await user_repository.get_user_by_email(db, email):
        raise AppError(409, "AUTH_EMAIL_DUPLICATED", "이미 가입된 이메일입니다.")

    try:
        user = await user_repository.create_user_with_profile(db, email, hash_password(password), birth_date)
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
    if user is None or user.status == "deleted" or not verify_password(password, user.password_hash):
        raise INVALID_LOGIN
    # 비밀번호까지 맞은 본인에게만 이유를 알려준다
    if user.status == "pending_guardian":
        raise AppError(403, "AUTH_GUARDIAN_PENDING", "법정대리인 동의가 확인된 뒤 이용할 수 있습니다.")
    return await _issue_tokens(db, user.user_id)

async def get_me(db: AsyncSession, user_id: str) -> MeResult:
    user = await user_repository.get_user_by_id(db, user_id)
    profile = await user_repository.get_profile(db, user_id)
    if user is None or profile is None or user.status != "active":
        raise AppError(401, "AUTH_UNAUTHORIZED", "다시 로그인해 주세요.")
    return MeResult(
        user_id=user.user_id,
        email=user.email,
        sex=profile.sex,
        birth_date=profile.birth_date,
    )

async def update_me(db: AsyncSession, user_id: str, sex: str | None, birth_date: date | None = None) -> MeResult:
    """내 프로필 고치기: 성별·생년월일 (보낸 것만)."""
    profile = await user_repository.get_profile(db, user_id)
    if profile is None:
        raise AppError(401, "AUTH_UNAUTHORIZED", "다시 로그인해 주세요.")
    if sex is not None:
        profile.sex = sex
    if birth_date is not None:
        today = utcnow().date()
        if birth_date > today:
            raise AppError(422, "AUTH_INVALID_BIRTH_DATE", "생년월일을 확인해 주세요.")
        if _age_on(birth_date, today) < MIN_AGE:
            raise AppError(403, "AUTH_ADULT_ONLY", "만 19세 이상만 이용할 수 있습니다.")
        profile.birth_date = birth_date
    await db.commit()
    return await get_me(db, user_id)

async def refresh(db: AsyncSession, refresh_token: str) -> TokenResult:
    """쿠폰을 내면 새 팔찌 + 새 쿠폰. 쓴 쿠폰은 버린다."""
    session = await user_repository.get_session_by_token_hash(db, hash_token(refresh_token))
    now = utcnow()

    # 1. 그런 쿠폰이 있나?  2. 아직 안 버렸나?  3. 아직 안 지났나?
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise AppError(401, "AUTH_INVALID_REFRESH_TOKEN", "다시 로그인해 주세요.")

    # 쓴 쿠폰 버리기 (구멍 뚫기)
    session.revoked_at = now
    return await _issue_tokens(db, session.user_id)

async def logout(db: AsyncSession, user_id: str, refresh_token: str) -> None:
    """쿠폰 버리기. 내 쿠폰이고 아직 안 버렸을 때만."""
    session = await user_repository.get_session_by_token_hash(db, hash_token(refresh_token))
    if session is not None and session.user_id == user_id and session.revoked_at is None:
        session.revoked_at = utcnow()
        await db.commit()