"""이용 정지: 정지 기간 안의 회원은 로그인도, 이미 받은 로그인으로 하는 요청도 막는다."""
from datetime import datetime

from app.core.errors import AppError
from app.core.security import utcnow

FOREVER = datetime(9999, 12, 31)


def is_suspended(user) -> bool:
    return user.suspended_until is not None and user.suspended_until > utcnow()


def check(user) -> None:
    if is_suspended(user):
        until = "무기한" if user.suspended_until >= FOREVER else f"{user.suspended_until:%Y.%m.%d}까지"
        raise AppError(403, "ACCOUNT_SUSPENDED", f"이용이 정지된 계정이에요 ({until}). 문의가 있으면 비회원 문의로 남겨 주세요.")
