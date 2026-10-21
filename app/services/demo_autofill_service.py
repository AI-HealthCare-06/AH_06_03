"""체험용 자동 채움: 3일치 기록을 남기면 나머지 4주를 그 달성 비율대로 채우고 사이클을 끝낸다.
지인 체험(약 4일)에서 4주 전·후 비교를 보게 하려는 임시 기능이라 DEMO_AUTOFILL=1일 때만 동작한다.
채운 기록은 note에 MARK를 남겨 구분한다(사이클·기록은 탈퇴·동의 철회 때 함께 지워진다)."""
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import utcnow
from app.models.challenge import ChallengeCycle
from app.models.health import HealthRecord
from app.repositories import challenge_repository
from app.services import challenge_service

MARK = "[체험 자동 채움]"
MIN_DAYS = 3        # 기록한 날이 이만큼 되면 채운다
CYCLE_DAYS = 28


async def maybe_autofill(db: AsyncSession, cycle: ChallengeCycle) -> bool:
    """채웠으면 True. 꺼져 있거나 기록한 날이 모자라거나 이미 채웠으면 False."""
    if not settings.DEMO_AUTOFILL:
        return False
    missions = await challenge_repository.get_cycle_missions(db, cycle.cycle_id)
    logs = await challenge_repository.get_logs(db, [cc.cycle_challenge_id for cc, _ in missions])
    if any(l.note == MARK for l in logs):
        return False
    days = {l.log_date for l in logs}
    if len(days) < MIN_DAYS:
        return False

    # 오늘이 마지막 날인 28일 구간으로 사이클을 옮긴다(기록한 날은 모두 이 구간 안).
    today, now = challenge_service.today_kst(), utcnow()
    cycle.started_on, cycle.ended_on = today - timedelta(days=CYCLE_DAYS - 1), today
    await db.execute(  # 4주 재입력이 찾는 기준 건강기록(시작일 이전 입력)이 옮긴 시작일보다 늦지 않게 맞춘다
        update(HealthRecord)
        .where(HealthRecord.user_id == cycle.user_id, HealthRecord.cycle_id.is_(None),
               HealthRecord.input_type.in_(["initial", "interim_reassessment", "full_reassessment"]),
               HealthRecord.examination_date > cycle.started_on)
        .values(examination_date=cycle.started_on)
    )

    span = [cycle.started_on + timedelta(days=i) for i in range(CYCLE_DAYS)]
    for cc, _ in missions:
        mine = [l for l in logs if l.cycle_challenge_id == cc.cycle_challenge_id]
        done = [l for l in mine if l.status == "completed"]
        if not done:
            continue                                             # 한 번도 못 한 미션은 채우지 않는다(0%로 둔다)
        template = done[0]
        taken = {l.log_date for l in mine}
        free = [d for d in span if d not in taken]
        want = min(len(free), max(0, round(len(done) / len(days) * CYCLE_DAYS) - len(done)))
        for i in range(want):                                    # 빈 날에 고르게 흩뿌려 주마다 비슷하게
            challenge_repository.add_log(db, cc.cycle_challenge_id, free[i * len(free) // want], {
                "status": "completed", "answer": template.answer, "quantity": template.quantity,
                "limit_exceeded": False, "note": MARK,
            }, now)
    await db.flush()
    await challenge_service.finalize_cycle(db, cycle)
    return True
