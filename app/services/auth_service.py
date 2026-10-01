""" 회원가입/로그인 매니저, 판단을 한다 """
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password, utcnow
from app.repositories import user_repository
from app.schemas.auth import SignupResult

MIN_AGE =14

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

