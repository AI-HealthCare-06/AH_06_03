"""체험이 끝난 뒤 탈퇴하지 않은 체험 이용자의 정보를 삭제한다 (처리방침 제3조·제7조, 2026-11-01까지).

가입 시각으로 대상을 고르고, 회원 탈퇴와 같은 삭제(account_service.delete_account_data)를 쓴다.
그래서 처리방침대로 로그인 기록(access_logs, 3개월)과 관리자 기록(2년·3년)은 남고, 나머지는 지워진다.

  # 1) 미리보기 (기본): 이메일은 보여 주지 않고 회원 번호 끝 8자리·가입 시각·이메일 도메인만
  python -m app.scripts.purge_trial_accounts --since 2026-10-22
  # 2) 실제 삭제: 미리보기에서 본 인원을 --confirm에 넣어야 한다 (다르면 아무것도 안 지움)
  python -m app.scripts.purge_trial_accounts --since 2026-10-22 --apply --confirm 27

관리자(서버 .env의 ADMIN_EMAILS) 계정은 늘 빠진다. 시연용 계정처럼 남길 도메인은 --keep-domain example.com.
"""
import argparse
import asyncio
from collections import Counter
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.core import pii
from app.core.config import settings
from app.core.db.databases import async_get_db
from app.models.user import User
from app.services import account_service


def kst_start(day: date) -> datetime:
    """한국 날짜의 0시를 DB 시각(UTC, 시간대 없음)으로."""
    return datetime.combine(day, time.min) - timedelta(hours=9)


def domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower() if "@" in email else "?"


async def find_targets(db, since: date, until: date | None, keep_domains: set[str]) -> tuple[list[User], int]:
    """대상 회원과, 관리자·남길 도메인이라 빠진 수."""
    q = select(User).where(User.status != "deleted", User.created_at >= kst_start(since))
    if until:
        q = q.where(User.created_at < kst_start(until + timedelta(days=1)))
    users = (await db.execute(q.order_by(User.created_at, User.user_id))).scalars().all()
    admins = settings.admin_email_set
    targets = [u for u in users if pii.normalize_email(u.email) not in admins and domain_of(u.email) not in keep_domains]
    return targets, len(users) - len(targets)


async def main(since: date, until: date | None, keep_domains: set[str], apply: bool, confirm: int | None) -> int:
    async for db in async_get_db():
        return await run(db, since, until, keep_domains, apply, confirm)
    return 1


async def run(db, since: date, until: date | None, keep_domains: set[str], apply: bool, confirm: int | None) -> int:
    if True:
        targets, skipped = await find_targets(db, since, until, keep_domains)
        period = f"{since} ~ {until or '지금'}"
        print(f"가입일 {period} (한국 시각) · 대상 {len(targets)}명 · 관리자·남길 도메인으로 빠진 {skipped}명")
        print("가입일별:", dict(sorted(Counter((u.created_at + timedelta(hours=9)).strftime("%m-%d") for u in targets).items())))
        print("도메인별:", dict(Counter(domain_of(u.email) for u in targets).most_common()))
        for u in targets:
            print(f"  {u.user_id[-8:]}  {(u.created_at + timedelta(hours=9)):%m-%d %H:%M}  {u.status:9s} {domain_of(u.email)}")

        if not apply:
            print(f"\n미리보기예요. 진짜 지우려면 --apply --confirm {len(targets)} 를 붙이세요.")
            return 0
        if confirm != len(targets):
            print(f"\n확인 인원({confirm})이 대상({len(targets)})과 달라서 아무것도 지우지 않았어요. 미리보기를 다시 보세요.")
            return 2

        ids = [u.user_id for u in targets]          # commit 뒤에는 객체가 버려지므로 번호만 메모
        done, failed = 0, []
        for user_id in ids:
            try:
                user = await db.get(User, user_id, populate_existing=True)
                await account_service.delete_account_data(db, user)
                await db.commit()
                done += 1
            except Exception as e:  # 한 명이 실패해도 나머지는 계속
                await db.rollback()
                failed.append((user_id[-8:], type(e).__name__))
        print(f"\n삭제 완료 {done}명, 실패 {len(failed)}명")
        for short, err in failed:
            print(f"  실패: {short} → {err}")
        return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="체험 이용자 정보 삭제 (처리방침 제3조·제7조)")
    parser.add_argument("--since", type=date.fromisoformat, required=True, help="가입일 시작(한국 날짜, 포함)")
    parser.add_argument("--until", type=date.fromisoformat, help="가입일 끝(한국 날짜, 포함). 비우면 지금까지")
    parser.add_argument("--keep-domain", action="append", default=[], help="남길 이메일 도메인(예: example.com)")
    parser.add_argument("--apply", action="store_true", help="진짜로 삭제")
    parser.add_argument("--confirm", type=int, help="미리보기에서 본 대상 인원(--apply와 함께 필수)")
    a = parser.parse_args()
    raise SystemExit(asyncio.run(main(a.since, a.until, {d.lower() for d in a.keep_domain}, a.apply, a.confirm)))
