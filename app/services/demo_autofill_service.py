"""체험용 자동 채움: 3일치 기록을 남기면 나머지 4주(28일 모두)를 그 달성 비율대로 완료·못 함으로 채우고 사이클을 끝낸다.
지인 체험(약 4일)에서 4주 전·후 비교를 보게 하려는 임시 기능이라 DEMO_AUTOFILL=1일 때만 동작한다.
채운 기록은 note에 MARK를 남겨 구분한다(사이클·기록은 탈퇴·동의 철회 때 함께 지워진다)."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import utcnow
from app.models.challenge import ChallengeCycle
from app.models.health import HealthRecord
from app.repositories import challenge_repository
from app.services import challenge_reward_service, challenge_rules as rules, challenge_service

MARK = "[체험 자동 채움]"
MIN_DAYS = 3        # 기록한 날이 이만큼 되면 채운다
CYCLE_DAYS = 28


# 미션별로 "못 한 날"의 응답: 규칙(evaluate_log)을 거쳐 저장값을 만든다
FAIL = {"SMK-1": ("smoked", None), "NA-1": ("finished", None), "NA-2": ("added", None), "ACT-2": ("none", None),
        "ACT-3": ("none", None), "OUT-1": ("not_requested", None), "BRK-1": ("skipped", None), "WT-1": ("no", None),
        "ACT-1": (None, 0)}


def _failed_values(code: str, sex: str, cfg: dict | None) -> dict:
    answer, quantity = FAIL.get(code, (None, None))
    if code == "ALC-1":
        quantity = ((cfg or {}).get("male_max", 2) if sex == "male" else (cfg or {}).get("female_max", 1)) + 1
    v = rules.evaluate_log(code, answer, quantity, sex, cfg)
    return {**v, "answer": answer}


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
    # 그날 미션을 모두 기록했을 때만 채운다(첫 미션만 체크했는데 사이클이 끝나 버리면 나머지 미션을 못 하므로)
    today_logged = {l.cycle_challenge_id for l in logs if l.log_date == challenge_service.today_kst()}
    if any(cc.cycle_challenge_id not in today_logged for cc, _ in missions):
        return False

    # 오늘이 마지막 날인 28일 구간으로 사이클을 옮긴다(기록한 날은 모두 이 구간 안).
    today, now = challenge_service.today_kst(), utcnow()
    cycle.started_on, cycle.ended_on = today - timedelta(days=CYCLE_DAYS - 1), today
    # 4주 재입력이 찾는 기준 건강기록(시작일 이전 입력)이 옮긴 시작일보다 늦지 않게, 가장 이른 처음 입력 하나만 시작일로 당긴다.
    # (여러 건을 같은 날짜로 모으면 사용자·종류·날짜 중복 제약에 걸리므로 하나만 옮긴다.)
    recs = (await db.execute(
        select(HealthRecord).where(
            HealthRecord.user_id == cycle.user_id, HealthRecord.cycle_id.is_(None),
            HealthRecord.input_type.in_(["initial", "interim_reassessment", "full_reassessment"]),
        ).order_by(HealthRecord.examination_date)
    )).scalars().all()
    if recs and recs[0].examination_date > cycle.started_on:
        recs[0].examination_date = cycle.started_on

    span = [cycle.started_on + timedelta(days=i) for i in range(CYCLE_DAYS)]
    sex = await challenge_service._sex(db, cycle.user_id)
    for cc, ch in missions:
        mine = [l for l in logs if l.cycle_challenge_id == cc.cycle_challenge_id]
        done = [l for l in mine if l.status == "completed"]
        taken = {l.log_date for l in mine}
        free = [d for d in span if d not in taken]
        # 28일 모두 기록을 만든다: 사용자가 해낸 비율만큼은 완료, 나머지는 못 한 날
        want_done = min(len(free), max(0, round(len(done) / len(days) * CYCLE_DAYS) - len(done))) if done else 0
        done_days = {free[i * len(free) // want_done] for i in range(want_done)} if want_done else set()
        for d in free:
            if d in done_days:
                v = {"status": "completed", "answer": done[0].answer, "quantity": done[0].quantity, "limit_exceeded": False}
            else:
                v = _failed_values(ch.challenge_code, sex, cc.target_config)
            challenge_repository.add_log(db, cc.cycle_challenge_id, d, {**v, "note": MARK}, now)
    await db.flush()
    for d in span:      # 채운 날도 기록 보상(그날 모두 완료 +5, 5일마다 +10)을 준다 — 배지만 차고 파이는 모자라 보이지 않게
        await challenge_reward_service.reward_after_log(db, cycle.user_id, d)
    await challenge_service.finalize_cycle(db, cycle)
    return True
