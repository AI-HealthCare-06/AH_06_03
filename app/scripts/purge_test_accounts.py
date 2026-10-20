"""탈퇴하지 않은 테스트 계정을 한 번에 탈퇴 처리한다.

기본은 미리보기. 진짜 지우려면 --apply.
  python -m app.scripts.purge_test_accounts --pattern "%@a.com"
  python -m app.scripts.purge_test_accounts --pattern "%@a.com" --pattern "test%@%" --apply
"""
import argparse
import asyncio

from sqlalchemy import or_, select

from app.core.config import settings

from app.core.db.databases import async_get_db
from app.models.user import User
from app.services import account_service


def _check_patterns(patterns: list[str]) -> None:
    for p in patterns:
        if "@" not in p or p.replace("%", "").replace("_", "") in {"", "@"}:
            raise SystemExit(f"너무 넓은 패턴이에요: {p!r}  (예: %@a.com)")


async def main(patterns: list[str], apply: bool) -> None:
    _check_patterns(patterns)
    async for db in async_get_db():
        users = (await db.execute(
            select(User)
            .where(User.status != "deleted")
            .where(or_(*[User.email.like(p) for p in patterns]))
            .order_by(User.email)
        )).scalars().all()

        print(f"대상 {len(users)}명")
        for u in users:
            print(f"  {u.email}  ({u.status})")

        if not apply:
            print("\n미리보기예요. 진짜 지우려면 --apply 를 붙이세요.")
            return

        # commit/rollback 뒤에는 u의 정보가 버려지므로, 번호와 이메일을 미리 메모해 둔다
        targets = [(u.user_id, u.email) for u in users]

        done, failed = 0, []
        for user_id, email in targets:
            try:
                user = await db.get(User, user_id, populate_existing=True)   # 매번 DB에서 새로 꺼내기
                await account_service.delete_account_data(db, user)
                await db.commit()
                done += 1
            except Exception as e:  # 한 명이 실패해도 나머지는 계속
                await db.rollback()
                failed.append((email, repr(e)))
        print(f"\n완료 {done}명, 실패 {len(failed)}명")
        for email, err in failed:
            print(f"  실패: {email} → {err}")
        break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", action="append", required=True, help='이메일 LIKE 패턴, 예: "%%@a.com"')
    parser.add_argument("--apply", action="store_true", help="진짜로 탈퇴 처리")
    args = parser.parse_args()
    asyncio.run(main(args.pattern, args.apply))

def _admin_emails() -> list[str]:
    """관리자 목록은 관리자 창구와 같은 설정(settings.admin_email_set)을 쓴다."""
    emails = sorted(settings.admin_email_set)
    if not emails:
        print("⚠️  ADMIN_EMAILS가 비어 있어요. 관리자 계정이 자동 제외되지 않아요.\n")
    return emails