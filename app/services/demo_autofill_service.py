"""체험용 자동 채움: 서로 다른 3일을 기록하면 나머지 4주(28일 모두)를 세 가지 패턴(꾸준함 / 중간에 흔들림 / 후반에 놓침) 중 하나로 채우고 사이클을 끝낸다.
사용자의 3일 기록은 결과를 정하지 않는다(3일을 다 한 사람이 모두 "완주"로만 나오면 못 한 날·미완료 화면을 아무도 못 보므로).
결과는 채운 순서대로 꾸준함 → 중간에 흔들림 → 후반에 놓침을 돌아가며 배정한다(사람이 적어도 골고루 나오게).
지인 체험(나흘)에서 4주 전·후 비교를 보게 하려는 임시 기능이라 DEMO_AUTOFILL=1일 때만 동작하고, DEMO_AUTOFILL_END가 지나면 멈춘다.
채운 기록은 note에 MARK와 패턴을 남겨 구분한다(사이클·기록은 탈퇴·동의 철회 때 함께 지워진다)."""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import utcnow
from app.models.challenge import ChallengeCycle, ChallengeLog, CycleChallenge
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


# 4주 동안 주마다 "해낸 날"(7일 중). 미션의 주간 목표가 3·5·7이어도 판정이 같도록 목표에 비례해 채운다(week_goal).
# 판정: 꾸준함·중간에 흔들림은 완주, 후반에 놓침은 미완료(목표 미달). 4주차는 직접 기록한 3일이 들어가 있다.
PATTERNS = {
    "steady": [7, 7, 7, 7],    # 꾸준함: 매일
    "wobble": [7, 6, 6, 7],    # 중간에 흔들림: 2·3주차만 주 6일
    "fade": [7, 4, 2, 1],      # 후반에 놓침: 갈수록 줄어듦
}
ORDER = list(PATTERNS)         # 채운 순서대로 돌아가며 배정


def week_goal(pattern: str, days: int, weekly_target: int) -> int:
    """그 주에 해낸 날 수. 꾸준함·중간에 흔들림은 표대로, 후반에 놓침은 주간 목표가 작은 미션이 완주로 나오지 않게 목표의 days/7로 줄인다."""
    return min(days, round(days / 7 * weekly_target)) if pattern == "fade" else days


def split_note(note: str | None) -> str | None:
    """채운 기록의 note에서 패턴 이름. 채운 기록이 아니면 None. (옛 형식 MARK만 있으면 steady로 본다)"""
    if not note or not note.startswith(MARK):
        return None
    tail = note[len(MARK):].strip()
    return tail if tail in PATTERNS else "steady"


def ended(today: date) -> bool:
    """체험 마지막 날(DEMO_AUTOFILL_END)이 지났는가. 날짜를 안 정했으면 끝나지 않는다."""
    end = settings.demo_end
    return end is not None and today > end


async def next_pattern(db: AsyncSession) -> str:
    """지금까지 채운 사이클 수로 다음 패턴을 정한다."""
    n = (await db.execute(
        select(func.count(func.distinct(CycleChallenge.cycle_id)))
        .join(ChallengeLog, ChallengeLog.cycle_challenge_id == CycleChallenge.cycle_challenge_id)
        .where(ChallengeLog.note.like(MARK + "%"))
    )).scalar_one()
    return ORDER[n % len(ORDER)]


async def pattern_of(db: AsyncSession, cycle_id: str) -> str | None:
    """이 사이클에 자동 채움 기록이 있으면 그때 쓴 패턴 이름, 없으면 None (비교 화면에서 가상 기록이 섞였다고 알리는 데 쓴다)."""
    missions = await challenge_repository.get_cycle_missions(db, cycle_id)
    logs = await challenge_repository.get_logs(db, [cc.cycle_challenge_id for cc, _ in missions])
    return next((p for p in (split_note(l.note) for l in logs) if p), None)


async def record_days(db: AsyncSession, cycle: ChallengeCycle) -> tuple[list, list, set[date]]:
    """(미션들, 기록들, 기록한 날짜들). 미션을 하나라도 기록한 날이 기록일이다."""
    missions = await challenge_repository.get_cycle_missions(db, cycle.cycle_id)
    logs = await challenge_repository.get_logs(db, [cc.cycle_challenge_id for cc, _ in missions])
    return missions, logs, {l.log_date for l in logs}


async def maybe_autofill(db: AsyncSession, cycle: ChallengeCycle, finish: bool = False) -> str | None:
    """채웠으면 쓴 패턴 이름. 꺼져 있거나 체험이 끝났거나 이미 채웠거나 기록일이 모자라면 None.
    finish=False(기록할 때): 3번째 기록일에 그날 미션을 모두 기록했을 때만 채운다.
    finish=True(결과 보기 버튼): 기록일이 3일이면 미션이 남았어도 채운다."""
    today = challenge_service.today_kst()
    if not settings.DEMO_AUTOFILL or ended(today):
        return None
    missions, logs, days = await record_days(db, cycle)
    if any(split_note(l.note) for l in logs) or len(days) < MIN_DAYS:
        return None
    if not finish:
        today_logged = {l.cycle_challenge_id for l in logs if l.log_date == today}
        if today not in days or len(days) != MIN_DAYS or any(cc.cycle_challenge_id not in today_logged for cc, _ in missions):
            return None
    return await fill(db, cycle, missions, logs, days)


async def fill(db: AsyncSession, cycle: ChallengeCycle, missions: list, logs: list, days: set[date]) -> str:
    """28일을 채운다. 직접 기록한 날(days)에 그 미션을 기록하지 않았다면 \"못 한 날\"로 고정한다(실제 기록 날에 가상으로 \"한 날\"을 만들지 않는다)."""
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
    pattern = await next_pattern(db)
    for cc, ch in missions:
        mine = {l.log_date: l for l in logs if l.cycle_challenge_id == cc.cycle_challenge_id}
        for w, wdays in enumerate(PATTERNS[pattern]):
            week = span[w * 7:(w + 1) * 7]
            have = sum(1 for d in week if d in mine and mine[d].status == "completed")
            free = [d for d in week if d not in mine and d not in days]
            need = min(len(free), max(0, week_goal(pattern, wdays, cc.weekly_target) - have))
            done_days = {free[k * len(free) // need] for k in range(need)} if need else set()
            for d in (d for d in week if d not in mine):   # 빈 날은 모두 기록을 만든다: 해낸 날 또는 못 한 날(직접 기록한 날의 빈 미션은 항상 못 한 날)
                v = _done_values(ch.challenge_code, sex, cc.target_config) if d in done_days                     else _failed_values(ch.challenge_code, sex, cc.target_config)
                challenge_repository.add_log(db, cc.cycle_challenge_id, d, {**v, "note": f"{MARK} {pattern}"}, now)
    await db.flush()
    for d in span:      # 채운 날도 기록 보상(그날 모두 완료 +5, 5일마다 +10)을 준다 — 배지만 차고 파이는 모자라 보이지 않게
        await challenge_reward_service.reward_after_log(db, cycle.user_id, d)
    await challenge_service.finalize_cycle(db, cycle)
    return pattern
