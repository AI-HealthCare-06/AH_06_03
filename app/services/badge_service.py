"""배지 12종. 표 없이 챌린지·건강 기록으로 볼 때마다 계산한다.
기록이 지워지면(탈퇴·건강정보 동의 철회) 배지도 자연히 사라진다."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge, ChallengeCategory, ChallengeCycle, ChallengeLog, CycleChallenge
from app.models.health import HealthMeasurement, HealthRecord
from app.services import streak_service

# (코드, 이름, 묶음, 안내 문구) — 화면 순서 그대로
BADGES = [
    ("first", "첫 인증", "streak", "챌린지를 한 번 인증하면 열려요"),
    ("streak_3", "3일 연속", "streak", "3일 연속을 채우면 열려요"),
    ("streak_5", "5일 연속", "streak", "5일 연속을 채우면 열려요"),
    ("streak_7", "7일 연속", "streak", "7일 연속을 채우면 열려요"),
    ("streak_14", "14일 연속", "streak", "14일 연속을 채우면 열려요"),
    ("streak_28", "28일 연속", "streak", "28일 연속을 채우면 열려요"),
    ("week_1", "1주 완주", "record", "한 주의 목표를 모두 채우면 열려요"),
    ("exercise_10", "운동 10회", "record", "신체 활동 미션을 10번 완료하면 열려요"),
    ("bp_4", "혈압 기록 4회", "record", "처음 입력과 4주 재입력에서 혈압을 4번 기록하면 열려요"),
    ("cycle_1", "1차 완주", "record", "첫 4주 챌린지를 완주하면 열려요"),
    ("cycle_2", "2차 완주", "record", "두 번째 4주 챌린지를 완주하면 열려요"),
    ("cycle_12w", "12주 완주", "record", "세 번의 4주 챌린지를 모두 완주하면 열려요"),
]
EXERCISE_CATEGORY = "ACTIVITY"   # 신체 활동 카테고리 전체 (미션이 늘어도 고치지 않아도 됨)

async def _cycle_rows(db: AsyncSession, user_id: str):
    return (await db.execute(
        select(ChallengeCycle.cycle_id, ChallengeCycle.started_on, ChallengeCycle.ended_on, ChallengeCycle.status,
               CycleChallenge.cycle_challenge_id, CycleChallenge.weekly_target, Challenge.challenge_code,
               ChallengeLog.log_date, ChallengeLog.status)
        .join(CycleChallenge, CycleChallenge.cycle_id == ChallengeCycle.cycle_id)
        .join(Challenge, Challenge.challenge_id == CycleChallenge.challenge_id)
        .outerjoin(ChallengeLog, ChallengeLog.cycle_challenge_id == CycleChallenge.cycle_challenge_id)
        .where(ChallengeCycle.user_id == user_id)
    )).all()


def _first_full_week(cycles: dict) -> date | None:
    """한 주에 모든 미션이 주간 목표를 채운 가장 이른 날."""
    best = None
    for c in cycles.values():
        for w in range(4):
            ws = c["start"] + timedelta(days=7 * w)
            we = ws + timedelta(days=6)
            hits = []
            for target, dates in c["missions"].values():
                in_week = sorted(d for d in dates if ws <= d <= we)
                if len(in_week) < target:
                    break
                hits.append(in_week[target - 1])        # 그 미션이 목표를 채운 날
            else:
                if hits:
                    day = max(hits)                      # 마지막 미션까지 채운 날
                    best = day if best is None else min(best, day)
    return best


def _best_week(cycles: dict) -> tuple[int, int]:
    """가장 잘한 한 주에 주간 목표를 채운 미션 수와 전체 미션 수 (1주 완주 배지의 진행 정도)."""
    best, total = 0, 0
    for c in cycles.values():
        total = max(total, len(c["missions"]))
        for w in range(4):
            ws = c["start"] + timedelta(days=7 * w)
            we = ws + timedelta(days=6)
            hit = sum(1 for target, dates in c["missions"].values() if sum(1 for d in dates if ws <= d <= we) >= target)
            best = max(best, hit)
    return best, total


async def my_badges(db: AsyncSession, user_id: str) -> dict:
    rows = await _cycle_rows(db, user_id)
    earned: dict[str, date] = {}

    completed = sorted(r[7] for r in rows if r[7] is not None and r[8] == "completed")
    if completed:
        earned["first"] = completed[0]

    days = await streak_service.done_days(db, user_id)
    for n in (3, 5, 7, 14, 28):
        for start, length in streak_service.runs(days):
            if length >= n:
                earned[f"streak_{n}"] = start + timedelta(days=n - 1)
                break

    exercises = sorted(r[7] for r in rows if r[6] == EXERCISE_CATEGORY and r[7] is not None and r[8] == "completed")
    if len(exercises) >= 10:
        earned["exercise_10"] = exercises[9]

    cycles: dict = {}   # 사이클 → {"start": 시작일, "missions": {미션: (주간 목표, [completed 날짜])}}
    for cycle_id, started_on, _, _, cc_id, target, _, log_date, status in rows:
        c = cycles.setdefault(cycle_id, {"start": started_on, "missions": {}})
        m = c["missions"].setdefault(cc_id, (target, []))
        if log_date is not None and status == "completed":
            m[1].append(log_date)
    week = _first_full_week(cycles)
    if week is not None:
        earned["week_1"] = week

    finished = sorted({(r[0], r[2]) for r in rows if r[3] == "completed"}, key=lambda x: x[1])
    for i, code in enumerate(["cycle_1", "cycle_2", "cycle_12w"]):
        if len(finished) > i:
            earned[code] = finished[i][1]

    bp = (await db.execute(
        select(HealthRecord.examination_date).distinct()
        .join(HealthMeasurement, HealthMeasurement.health_record_id == HealthRecord.health_record_id)
        .where(HealthRecord.user_id == user_id,
               HealthRecord.input_type.in_(["initial", "interim_reassessment"]),
               HealthMeasurement.metric_code == "SBP")
        .order_by(HealthRecord.examination_date)
    )).scalars().all()
    if len(bp) >= 4:
        earned["bp_4"] = bp[3]

    # 받기까지 얼마나 왔는지 (화면이 파이 조각처럼 채워서 보여 준다): 코드 → (지금까지, 목표)
    longest = max((length for _, length in streak_service.runs(days)), default=0)
    week_hit, week_total = _best_week(cycles)
    progress = {"first": (len(completed), 1), "week_1": (week_hit, week_total or 3),
                "exercise_10": (len(exercises), 10), "bp_4": (len(bp), 4)}
    for n in (3, 5, 7, 14, 28):
        progress[f"streak_{n}"] = (longest, n)
    for i, code in enumerate(["cycle_1", "cycle_2", "cycle_12w"]):
        progress[code] = (len(finished), i + 1)
    badges = []
    for c, l, g, h in BADGES:
        done, goal = progress[c]
        got = c in earned
        badges.append({"code": c, "label": l, "group": g, "hint": h, "earned": got, "earned_on": earned.get(c),
                       "progress": goal if got else min(done, goal), "target": goal})
    nxt = next((b for b in badges if not b["earned"]), None)
    return {"earned_count": len(earned), "total": len(BADGES), "next": nxt, "badges": badges}

async def _cycle_rows(db: AsyncSession, user_id: str):
    return (await db.execute(
        select(ChallengeCycle.cycle_id, ChallengeCycle.started_on, ChallengeCycle.ended_on, ChallengeCycle.status,
               CycleChallenge.cycle_challenge_id, CycleChallenge.weekly_target, ChallengeCategory.category_code,
               ChallengeLog.log_date, ChallengeLog.status)
        .join(CycleChallenge, CycleChallenge.cycle_id == ChallengeCycle.cycle_id)
        .join(Challenge, Challenge.challenge_id == CycleChallenge.challenge_id)
        .join(ChallengeCategory, ChallengeCategory.category_id == Challenge.category_id)
        .outerjoin(ChallengeLog, ChallengeLog.cycle_challenge_id == CycleChallenge.cycle_challenge_id)
        .where(ChallengeCycle.user_id == user_id)
    )).all()