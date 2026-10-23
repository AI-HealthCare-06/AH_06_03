"""챌린지 리마인드 푸시: 저녁 8시(오늘 미션을 다 기록하지 않은 사람), 아침 8시(아침 식사 미션을 아직 기록하지 않은 사람).
정기 작업(app/scripts/send_reminders.py)이 부른다. 문구는 조건에 맞는 후보 중 무작위, 직전 문구는 피한다."""
import random
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models.challenge import Challenge, ChallengeCycle, ChallengeLog, CycleChallenge
from app.models.push import PushSetting, PushSubscription
from app.schemas.push import PushSettings
from app.services import push_service, streak_service

URL = "challenge-progress.html"
BREAKFAST_CODE = "BRK-1"

# (번호, 제목, 본문, 조건) — 조건: always(항상) / partial(오늘 일부 기록) / none(오늘 기록 없음) / streak(연속 1일 이상) / weekend(토·일)
EVENING = [
    (1, "오늘의 파이를 구워 볼까요? ✨", "미션을 기록하면 파이가 한 조각 완성돼요. 편할 때 들러 주세요.", "always"),
    (2, "파이 오븐이 예열됐어요 🔥", "오늘의 미션, 편할 때 천천히 기록해 주세요.", "always"),
    (3, "오늘 파이가 조금 남았어요 ⏰", "남은 미션을 기록하고 오늘의 파이를 완성해 봐요.", "partial"),
    (4, "오늘도 잘 해내고 계세요 👏", "기록 한 번이면 오늘 챌린지가 이어져요. 천천히 해 주세요.", "always"),
    (5, "어제까지 잘 이어 오셨어요 ✨", "오늘 기록을 남기면 연속 기록이 이어져요.", "streak"),
    (6, "하루 한 번, 가볍게 📝", "오늘의 건강 기록을 남겨 볼까요?", "none"),
    (7, "잠깐 들러 가세요 🙌", "오늘 미션 체크는 1분이면 끝나요.", "none"),
    (8, "쉬는 날이어도 괜찮아요 🌿", "기록할 수 있을 때 가볍게 남겨 주세요.", "weekend"),
]
BREAKFAST = [
    (1, "좋은 아침이에요 ☀️", "오늘 아침은 뭐 드셨어요? 먹고 나서 기록해 주세요.", "always"),
    (2, "아침밥 먹을 시간이에요 🍚", "간단하게라도 챙겨 먹으면 하루가 든든해요.", "always"),
    (3, "오늘 아침은 챙기셨나요? 🥪", "한 입이라도 좋아요. 먹고 나면 파이 한 조각이 구워져요 ✨", "always"),
    (4, "아침 파이가 구워지고 있어요 ✨", "아침 식사를 하고 기록하면 파이가 완성돼요.", "always"),
    (5, "파이도 아침이 필요해요 🍞", "맛있게 드시고 기록해 주세요.", "always"),
    (6, "오늘도 힘나는 하루 시작해요 💪", "든든한 아침 한 끼로 시작해 볼까요?", "always"),
    (7, "주말 아침이에요 ☕", "여유롭게 한 끼 챙겨 보세요.", "weekend"),
]


def pick(messages: list, conditions: set[str], last_id: int | None):
    """조건에 맞는 후보 중 무작위. 후보가 둘 이상이면 직전 문구는 뺀다."""
    cands = [m for m in messages if m[3] in conditions]
    if len(cands) > 1:
        cands = [m for m in cands if m[0] != last_id] or cands
    return random.choice(cands)


async def _subscribed_users(db: AsyncSession, kind: str) -> list[str]:
    """구독한 기기가 있고 그 종류를 꺼 두지 않은 사람 (설정 줄이 없으면 켜진 것으로 본다)."""
    users = set((await db.execute(select(PushSubscription.user_id).distinct())).scalars().all())
    off = set((await db.execute(select(PushSetting.user_id).where(getattr(PushSetting, kind).is_(False)))).scalars().all())
    return sorted(users - off)


@dataclass
class Stats:
    """정기 작업 결과 (사람 수, 만료 삭제·실패는 기기 수)."""
    targets: int = 0   # 조건에 맞는 사람
    sent: int = 0      # 받은 사람
    skipped: int = 0   # 오늘 이미 받아서 건너뛴 사람
    gone: int = 0      # 만료돼서 지운 구독
    failed: int = 0    # 실패한 기기


async def _send_one(db: AsyncSession, uid: str, kind: str, messages: list, cond: set[str], today: date, stats: Stats) -> None:
    """한 사람에게 하루 한 번만 보낸다. 받으면 문구 번호와 날짜를 저장한다(중간에 멈췄다 다시 돌려도 받은 사람만 빠진다)."""
    stats.targets += 1
    row = await db.get(PushSetting, uid)
    if row is not None and getattr(row, f"{kind}_sent_on") == today:
        stats.skipped += 1
        return
    mid, title, body, _ = pick(messages, cond, getattr(row, f"last_{kind}_id") if row else None)
    r = await push_service.send(db, uid, kind, title, body, URL)
    stats.gone += r.gone
    stats.failed += r.failed
    if r.sent:
        if row is None:
            row = PushSetting(user_id=uid, **PushSettings().model_dump(), updated_at=utcnow())
            db.add(row)
        setattr(row, f"last_{kind}_id", mid)
        setattr(row, f"{kind}_sent_on", today)
        await db.commit()
        stats.sent += 1


async def send_evening(db: AsyncSession, today: date) -> Stats:
    """저녁 리마인드: 진행 중 챌린지가 있고 오늘 미션을 다 기록하지 않은 사람."""
    stats = Stats()
    for uid in await _subscribed_users(db, "challenge"):
        done, total = await streak_service.today_progress(db, uid, today)
        if total == 0 or done >= total:
            continue
        streak = streak_service.current_streak(await streak_service.done_days(db, uid), today)
        cond = {"always", "partial" if done else "none"}
        if streak >= 1:
            cond.add("streak")
        if today.weekday() >= 5:
            cond.add("weekend")
        await _send_one(db, uid, "challenge", EVENING, cond, today, stats)
    return stats


async def _breakfast_mission(db: AsyncSession, user_id: str, today: date) -> str | None:
    """오늘 진행 중인 사이클에 아침 식사 미션이 있으면 그 미션 번호(cycle_challenge_id)."""
    return (await db.execute(
        select(CycleChallenge.cycle_challenge_id)
        .join(ChallengeCycle, ChallengeCycle.cycle_id == CycleChallenge.cycle_id)
        .join(Challenge, Challenge.challenge_id == CycleChallenge.challenge_id)
        .where(ChallengeCycle.user_id == user_id, ChallengeCycle.status == "active",
               ChallengeCycle.started_on <= today, ChallengeCycle.ended_on >= today,
               CycleChallenge.status == "active", Challenge.challenge_code == BREAKFAST_CODE)
    )).scalar_one_or_none()


async def send_breakfast(db: AsyncSession, today: date) -> Stats:
    """아침 식사 리마인드: 진행 중 챌린지에 아침 식사 미션이 있고, 오늘 그 미션을 아직 기록하지 않은 사람."""
    stats = Stats()
    for uid in await _subscribed_users(db, "breakfast"):
        cc_id = await _breakfast_mission(db, uid, today)
        if cc_id is None:
            continue
        logged = (await db.execute(select(ChallengeLog.challenge_log_id).where(
            ChallengeLog.cycle_challenge_id == cc_id, ChallengeLog.log_date == today))).first()
        if logged:
            continue
        cond = {"always", "weekend"} if today.weekday() >= 5 else {"always"}
        await _send_one(db, uid, "breakfast", BREAKFAST, cond, today, stats)
    return stats