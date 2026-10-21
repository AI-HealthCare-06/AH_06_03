"""체험용 자동 채움: 3일치 기록을 남기면 나머지 4주(28일 모두)를 세 가지 패턴(꾸준함 / 중간에 흔들림 / 후반에 놓침) 중 하나로 채우고 사이클을 끝낸다.
사용자의 3일 비율은 따르지 않는다(3일을 다 한 사람이 모두 "완주"로만 나오면 못 한 날·미완료 화면을 아무도 못 보므로). 패턴은 사이클 번호표로 정해 같은 사이클은 늘 같은 패턴이다.
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


# 미션별로 "한 날"의 응답
SUCCESS = {"SMK-1": ("not_smoked", None), "NA-1": ("left", None), "NA-2": ("not_added", None), "ACT-2": ("30plus", None),
           "ACT-3": ("all", None), "OUT-1": ("requested", None), "BRK-1": ("ate", None), "WT-1": ("yes", None)}


def _done_values(code: str, sex: str, cfg: dict | None) -> dict:
    answer, quantity = SUCCESS.get(code, (None, None))
    if code == "ALC-1":
        quantity = 0
    elif code == "ACT-1":
        quantity = (cfg or {}).get("steps_target", 0)
    v = rules.evaluate_log(code, answer, quantity, sex, cfg)
    return {**v, "answer": answer}


# 4주(주마다 7일) 동안 주별로 해낸 날의 비율. 실제 4주는 이렇게 흔들리는 경우가 많다.
PATTERNS = {
    "steady": [0.95, 0.9, 0.9, 0.95],    # 꾸준함: 거의 매일
    "wobble": [1.0, 0.6, 0.5, 0.9],      # 중간에 흔들림: 2~3주차에 줄었다가 회복
    "fade": [1.0, 0.75, 0.4, 0.15],      # 후반에 놓침: 갈수록 줄어듦
}


def pick_pattern(cycle_id: str) -> str:
    """사이클 번호표로 패턴을 정한다(무작위처럼 골고루, 같은 사이클은 늘 같은 패턴)."""
    return list(PATTERNS)[sum(ord(c) for c in cycle_id) % len(PATTERNS)]


async def pattern_of(db: AsyncSession, cycle_id: str) -> str | None:
    """이 사이클에 자동 채움 기록이 있으면 그때 쓴 패턴 이름, 없으면 None (비교 화면에서 가상 기록이 섞였다고 알리는 데 쓴다)."""
    missions = await challenge_repository.get_cycle_missions(db, cycle_id)
    logs = await challenge_repository.get_logs(db, [cc.cycle_challenge_id for cc, _ in missions])
    return pick_pattern(cycle_id) if any(l.note == MARK for l in logs) else None


async def maybe_autofill(db: AsyncSession, cycle: ChallengeCycle) -> str | None:
    """채웠으면 쓴 패턴 이름. 꺼져 있거나 기록한 날이 모자라거나 이미 채웠으면 None."""
    if not settings.DEMO_AUTOFILL:
        return None
    missions = await challenge_repository.get_cycle_missions(db, cycle.cycle_id)
    logs = await challenge_repository.get_logs(db, [cc.cycle_challenge_id for cc, _ in missions])
    if any(l.note == MARK for l in logs):
        return None
    days = {l.log_date for l in logs}
    if len(days) < MIN_DAYS:
        return None
    # 그날 미션을 모두 기록했을 때만 채운다(첫 미션만 체크했는데 사이클이 끝나 버리면 나머지 미션을 못 하므로)
    today_logged = {l.cycle_challenge_id for l in logs if l.log_date == challenge_service.today_kst()}
    if any(cc.cycle_challenge_id not in today_logged for cc, _ in missions):
        return None

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
    pattern = pick_pattern(cycle.cycle_id)
    for cc, ch in missions:
        mine = {l.log_date: l for l in logs if l.cycle_challenge_id == cc.cycle_challenge_id}
        for w, rate in enumerate(PATTERNS[pattern]):
            week = span[w * 7:(w + 1) * 7]
            have = sum(1 for d in week if d in mine and mine[d].status == "completed")
            free = [d for d in week if d not in mine]
            need = min(len(free), max(0, round(rate * 7) - have))
            done_days = {free[k * len(free) // need] for k in range(need)} if need else set()
            for d in free:                      # 빈 날은 모두 기록을 만든다: 해낸 날 또는 못 한 날
                v = _done_values(ch.challenge_code, sex, cc.target_config) if d in done_days                     else _failed_values(ch.challenge_code, sex, cc.target_config)
                challenge_repository.add_log(db, cc.cycle_challenge_id, d, {**v, "note": MARK}, now)
    await db.flush()
    for d in span:      # 채운 날도 기록 보상(그날 모두 완료 +5, 5일마다 +10)을 준다 — 배지만 차고 파이는 모자라 보이지 않게
        await challenge_reward_service.reward_after_log(db, cycle.user_id, d)
    await challenge_service.finalize_cycle(db, cycle)
    return pattern
