""" 회원 창고 담당. DB에 넣고 꺼내는 일 수행. 판단은 서비스가 """
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserProfile

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