"""기간 안(한국 날짜)에 가입한 회원에게 감사의 의미로 파이를 지급한다.

기본은 미리보기. 진짜 지급하려면 --apply. 같은 이름(--key)으로 다시 돌려도 이미 받은 회원은 건너뛰어서(장부가 막는다),
기간이 끝난 뒤 한 번 더 돌려 늦게 가입한 사람까지 챙길 수 있다.
  python -m app.scripts.grant_thanks_pie --from 2026-10-22 --to 2026-10-23
  python -m app.scripts.grant_thanks_pie --from 2026-10-22 --to 2026-10-23 --amount 200 --apply
"""
import argparse
import asyncio
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.core.db.databases import async_get_db
from app.models.user import User
from app.services import pie_service

REASON = "thanks_first_day"


def kst_range_to_utc(start: date, end: date) -> tuple[datetime, datetime]:
    """한국 날짜 [start, end] 하루 전체를 UTC 구간 [시작, 끝)으로."""
    s = datetime(start.year, start.month, start.day) - timedelta(hours=9)
    e = datetime(end.year, end.month, end.day) + timedelta(days=1) - timedelta(hours=9)
    return s, e


async def grant(db, start: date, end: date, amount: int, key: str, apply: bool) -> tuple[int, int]:
    """(대상 수, 새로 지급한 수). apply가 아니면 지급하지 않는다."""
    lo, hi = kst_range_to_utc(start, end)
    users = (await db.execute(
        select(User).where(User.status != "deleted", User.created_at >= lo, User.created_at < hi)
        .order_by(User.created_at, User.user_id)
    )).scalars().all()
    given = 0
    if apply:
        for u in users:
            if await pie_service.add(db, u.user_id, amount, REASON, key):
                given += 1
        await db.commit()
    return len(users), given


async def main(start: date, end: date, amount: int, key: str, apply: bool) -> None:
    async for db in async_get_db():
        total, given = await grant(db, start, end, amount, key, apply)
        print(f"대상 {total}명 ({start} ~ {end} 한국 날짜 가입, 탈퇴 제외)")   # 이메일은 잠겨 있어 출력하지 않는다
        if not apply:
            print("미리보기예요. 진짜 지급하려면 --apply 를 붙이세요.")
        else:
            print(f"{given}명에게 {amount}파이를 지급했어요. (이미 받은 {total - given}명은 건너뜀)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=date.fromisoformat, required=True)
    ap.add_argument("--to", dest="end", type=date.fromisoformat, required=True)
    ap.add_argument("--amount", type=int, default=200)
    ap.add_argument("--key", default="2026-10", help="같은 지급인지 구분하는 이름 (바꾸면 다시 지급된다)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.end < a.start or a.amount <= 0:
        raise SystemExit("기간 또는 금액이 올바르지 않아요.")
    asyncio.run(main(a.start, a.end, a.amount, a.key, a.apply))
