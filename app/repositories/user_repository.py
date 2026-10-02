""" 회원 창고 담당. DB에 넣고 꺼내는 일 수행. 판단은 서비스가 """
from datetime import date,datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserProfile, UserSession, GuardianConsentVerification

# 이메일로 회원 찾기
async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result=await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

# 회원 카드와 프로필 같이 만들기
async def create_user_with_profile(
        db: AsyncSession, email: str, password_hash: str, birth_date: date, status: str = "active") -> User:

    user=User(email=email, password_hash=password_hash, status=status)
    db.add(user)
    await db.flush()
    db.add(UserProfile(user_id=user.user_id, birth_date=birth_date))
    return user

# 로그인 성공 후 세션 만들기
async def create_session(
    db: AsyncSession, user_id: str, refresh_token_hash: str, expires_at: datetime, now: datetime
) -> UserSession:
    """로그인 기록(쿠폰)을 만든다. 저장 확정(commit)은 서비스가 한다."""
    session = UserSession(
        user_id=user_id, refresh_token_hash=refresh_token_hash, expires_at=expires_at, created_at=now
    )
    db.add(session)
    return session

async def create_guardian_verification(
    db: AsyncSession,
    user_id: str,
    name_enc: str,
    relation: str,
    contact_enc: str,
    method: str,
    now: datetime,
    purge_due_at: datetime,
) -> GuardianConsentVerification:
    """보호자 동의 기록을 '확인 대기'로 만든다. 이름·연락처는 이미 암호화된 값을 받는다."""
    record = GuardianConsentVerification(
        user_id=user_id,
        guardian_name_enc=name_enc,
        guardian_relation=relation,
        guardian_contact_enc=contact_enc,
        verification_method=method,
        collected_at=now,
        purge_due_at=purge_due_at,
    )
    db.add(record)
    return record

async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    return await db.get(User, user_id)


async def get_profile(db: AsyncSession, user_id: str) -> UserProfile | None:
    return await db.get(UserProfile, user_id)
