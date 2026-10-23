"""정기 작업: 챌린지 리마인드 푸시 보내기.

  python -m app.scripts.send_reminders --kind breakfast   # 매일 08:00 (KST)
  python -m app.scripts.send_reminders --kind evening     # 매일 20:00 (KST)

한국 시각으로 22시~다음 날 7시 사이에는 아무것도 보내지 않는다(밤늦게·새벽 알림 금지).
"""
import argparse
import asyncio
import sys
from datetime import timedelta

from app.core.db.databases import async_get_db
from app.core.security import utcnow
from app.services import reminder_service
from app.services.challenge_service import today_kst

QUIET_FROM, QUIET_UNTIL = 22, 7   # 22:00 ~ 07:00 (KST)에는 보내지 않는다


async def main(kind: str) -> int:
    """돌린 결과를 개수로만 출력한다. 실패가 있거나 오류가 나면 1을 돌려준다(cron이 알림을 보내게)."""
    hour = (utcnow() + timedelta(hours=9)).hour
    if hour >= QUIET_FROM or hour < QUIET_UNTIL:      # 07:00 정각은 보낸다 (hour < 7만 막음)
        print(f"{kind}: 지금은 {hour}시(KST)라 보내지 않음")
        return 0
    try:
        async for db in async_get_db():
            send = reminder_service.send_breakfast if kind == "breakfast" else reminder_service.send_evening
            s = await send(db, today_kst())
            print(f"{kind}: 대상 {s.targets} / 보냄 {s.sent} / 건너뜀 {s.skipped} / 만료 삭제 {s.gone} / 실패 {s.failed}")
            return 1 if s.failed else 0
    except Exception as e:
        print(f"{kind}: 오류 {type(e).__name__}")
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["evening", "breakfast"], required=True)
    sys.exit(asyncio.run(main(parser.parse_args().kind)))