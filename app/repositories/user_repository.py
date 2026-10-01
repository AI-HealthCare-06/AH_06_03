""" 회원 창고 담당. DB에 넣고 꺼내는 일 수행. 판단은 서비스가 """
from datetime import date,datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserProfile, UserSession

# 이메일로 회원 찾기
async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result=await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

# 회원 카드와 프로필 같이 만들기
async def create_user_with_profile(
        db: AsyncSession, email: str, password_hash: str, birth_date: date) -> User:

    user=User(email=email, password_hash=password_hash)
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