"""관리자 운영 현황: 체험 진행 단계별 인원, 동의·삭제 현황, 서비스 상태, 집계 CSV.

이미 쌓인 기록을 세기만 하고, 이메일·사용자 번호 같은 알아볼 수 있는 값은 내보내지 않는다.
탈퇴한 사용자의 기록은 탈퇴 때 지워져서 자연히 빠진다.
"""
import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import utcnow
from app.models.access_log import AccessLog
from app.models.challenge import ChallengeCycle
from app.models.consent import ConsentPolicy, UserConsent
from app.models.deletion import AccountDeletionRequest
from app.models.eligibility import EligibilityAssessment
from app.models.health import HealthRecord
from app.models.prediction import Prediction
from app.models.survey import SurveyInstance
from app.models.user import User
from app.schemas.admin_overview import (
    ConsentCount, DailyActivity, DeletionEvent, DeletionStat, FunnelStage, Overview, ServiceStatus,
)
from app.services import admin_service

STARTED_AT = utcnow()   # 이 서버 프로세스가 켜진 시각
KST = timezone(timedelta(hours=9))

FUNNEL = [
    ("signup", "가입"),
    ("eligibility", "대상 확인"),
    ("health", "건강정보 입력"),
    ("survey", "설문 단계"),   # 설문은 건너뛸 수 있어서 "제출"이 아니라 "설문 단계를 지난 사람"
    ("prediction", "분석 결과"),
    ("challenge_started", "챌린지 시작"),
    ("challenge_completed", "4주 챌린지 완료"),
]


def _rate(part: int, whole: int | None) -> float | None:
    return round(part / whole, 3) if whole else None


async def _user_ids(db: AsyncSession, column, *conditions) -> set[str]:
    """조건에 맞는 사용자 번호 모음. 단계별 인원을 세는 데만 쓰고 응답에는 넣지 않는다."""
    query = select(column).distinct()
    if conditions:
        query = query.where(*conditions)
    return set((await db.execute(query)).scalars().all())


async def funnel(db: AsyncSession) -> list[FunnelStage]:
    active = await _user_ids(db, User.user_id, User.status == "active")
    records = {
        "eligibility": await _user_ids(db, EligibilityAssessment.user_id),
        "health": await _user_ids(db, HealthRecord.user_id),
        "survey": await _user_ids(db, SurveyInstance.user_id, SurveyInstance.status == "submitted"),
        "prediction": await _user_ids(db, Prediction.user_id, Prediction.status == "completed"),
        "challenge_started": await _user_ids(db, ChallengeCycle.user_id),
        "challenge_completed": await _user_ids(db, ChallengeCycle.user_id, ChallengeCycle.status == "completed"),
    }
    # "그 단계까지 간 사람" = 그 단계나 더 뒤 단계에 기록이 있는 사용자.
    # 앞 단계 기록이 없어도 뒤 단계에 왔으면 지나간 것으로 센다. 앞 단계 기록이 없는 경우:
    #   - 대상 확인 저장(2026-10-08) 전에 가입한 사람은 대상 확인 기록이 없다.
    #   - 동의를 철회했다가 다시 동의한 사람은 대상 확인 기록이 없을 수 있다.
    #   - 설문을 건너뛴 사람은 설문 제출 기록 없이 분석으로 넘어간다.
    # 그래서 아래 단계가 위 단계보다 많아지지 않는다(앞 단계 대비 100% 이하).
    # 정상(active) 회원만 센다. 그 밖의 계정은 이용할 수 없는 계정이라 뺀다(가입 숫자와 기준을 맞춤).
    counts, reached = {"signup": len(active)}, set()
    for code, _ in reversed(FUNNEL[1:]):
        reached |= records[code] & active
        counts[code] = len(reached)
    stages, previous = [], None
    for code, label in FUNNEL:
        n = counts[code]
        stages.append(FunnelStage(
            code=code, label=label, users=n, rate_of_signup=_rate(n, counts["signup"]),
            rate_of_previous=_rate(n, previous) if previous is not None else None,
        ))
        previous = n
    return stages


async def consents(db: AsyncSession) -> list[ConsentCount]:
    policies = (await db.execute(
        select(ConsentPolicy.policy_id, ConsentPolicy.policy_type, ConsentPolicy.version)
        .order_by(ConsentPolicy.policy_type, ConsentPolicy.version)
    )).all()
    counted = (await db.execute(
        select(UserConsent.policy_id, UserConsent.status, func.count()).group_by(UserConsent.policy_id, UserConsent.status)
    )).all()
    by_policy: dict[str, dict[str, int]] = {}
    for policy_id, status, n in counted:
        by_policy.setdefault(policy_id, {})[status] = int(n)
    return [
        ConsentCount(policy_type=ptype, version=version, agreed=by_policy.get(pid, {}).get("agreed", 0),
                     withdrawn=by_policy.get(pid, {}).get("withdrawn", 0))
        for pid, ptype, version in policies
    ]


def _sum_numbers(value) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        return sum(_sum_numbers(v) for v in value.values())
    if isinstance(value, list):
        return sum(_sum_numbers(v) for v in value)
    return 0


async def deletions(db: AsyncSession) -> DeletionStat:
    deleted = int((await db.execute(select(func.count()).select_from(User).where(User.status == "deleted"))).scalar_one())
    withdrawals = int((await db.execute(
        select(func.count()).select_from(UserConsent).where(UserConsent.status == "withdrawn")
    )).scalar_one())
    rows = (await db.execute(
        select(AccountDeletionRequest.completed_at, AccountDeletionRequest.result_summary)
        .where(AccountDeletionRequest.status == "completed")
        .order_by(AccountDeletionRequest.completed_at.desc()).limit(10)
    )).all()
    return DeletionStat(
        deleted_accounts=deleted, consent_withdrawals=withdrawals,
        recent=[DeletionEvent(completed_at=at, deleted_rows=_sum_numbers(summary)) for at, summary in rows],
    )


async def service_status(db: AsyncSession) -> ServiceStatus:
    db_ok, revision = True, None
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    try:
        revision = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
    except Exception:       # 마이그레이션 표가 없는 시험 환경 등
        await db.rollback()
    return ServiceStatus(
        server_started_at=STARTED_AT, uptime_seconds=int((utcnow() - STARTED_AT).total_seconds()),
        db_ok=db_ok, db_revision=revision, admin_count=len(settings.admin_email_set),
    )


def _kst_day(moment: datetime) -> date:
    """저장된 UTC 시각(시간대 표시 없음)이 한국 시각으로 어느 날짜인지."""
    return moment.replace(tzinfo=timezone.utc).astimezone(KST).date()


async def daily_activity(db: AsyncSession, days: int) -> list[DailyActivity]:
    """최근 days일의 날짜별 가입 수, 로그인 수, 로그인한 사용자 수, 재방문 사용자 수.

    로그인 기록(access_logs)은 개인을 알아볼 수 없는 숫자로만 쓰고, 93일이 지나면 자동으로 지워지므로 그 이전 날짜는 비어 있다.
    """
    today = _kst_day(utcnow())
    first_day = today - timedelta(days=days - 1)
    since_utc = datetime.combine(first_day, time.min, tzinfo=KST).astimezone(timezone.utc).replace(tzinfo=None)

    signup_times = (await db.execute(select(User.created_at).where(User.created_at >= since_utc))).scalars().all()
    login_rows = (await db.execute(
        select(AccessLog.account_id, AccessLog.created_at).where(AccessLog.event == "login").order_by(AccessLog.created_at)
    )).all()

    signups: dict[date, int] = {}
    for at in signup_times:
        signups[_kst_day(at)] = signups.get(_kst_day(at), 0) + 1
    first_login: dict[str, date] = {}
    per_day: dict[date, list[str]] = {}
    for account_id, at in login_rows:
        day = _kst_day(at)
        first_login.setdefault(account_id, day)
        per_day.setdefault(day, []).append(account_id)

    result = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        events = per_day.get(day, [])
        people = set(events)
        result.append(DailyActivity(
            date=day.isoformat(), signups=signups.get(day, 0), logins=len(events), active_users=len(people),
            returning_users=sum(1 for a in people if first_login[a] < day),
        ))
    return result


async def build_overview(db: AsyncSession, days: int = 14) -> Overview:
    return Overview(funnel=await funnel(db), consents=await consents(db), deletions=await deletions(db),
                    status=await service_status(db), activity=await daily_activity(db, days))


async def export_csv(db: AsyncSession) -> str:
    """집계 숫자만 담은 CSV. 사용자별 행은 내보내지 않는다."""
    overview = await build_overview(db, days=90)
    stats = await admin_service.challenge_stats(db)
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["meta", "generated_at_utc", utcnow().isoformat(timespec="seconds")])
    w.writerow([])
    w.writerow(["funnel", "code", "label", "users", "rate_of_signup", "rate_of_previous"])
    for s in overview.funnel:
        w.writerow(["funnel", s.code, s.label, s.users, _csv_num(s.rate_of_signup), _csv_num(s.rate_of_previous)])
    w.writerow([])
    w.writerow(["consent", "policy_type", "version", "agreed", "withdrawn"])
    for c in overview.consents:
        w.writerow(["consent", c.policy_type, c.version, c.agreed, c.withdrawn])
    w.writerow([])
    w.writerow(["daily", "date_kst", "signups", "logins", "active_users", "returning_users"])
    for d in overview.activity:
        w.writerow(["daily", d.date, d.signups, d.logins, d.active_users, d.returning_users])
    w.writerow([])
    w.writerow(["mission", "challenge_code", "challenge_name", "selected_count", "assigned_count", "completed_count",
                "incomplete_count", "stopped_count", "completion_rate", "giving_up_rate", "avg_logged_days", "avg_completed_days"])
    for m in stats.missions:
        w.writerow(["mission", m.challenge_code, m.challenge_name, m.selected_count, m.assigned_count, m.completed_count,
                    m.incomplete_count, m.stopped_count, _csv_num(m.completion_rate), _csv_num(m.giving_up_rate),
                    _csv_num(m.avg_logged_days), _csv_num(m.avg_completed_days)])
    return out.getvalue()


def _csv_num(value) -> str:
    return "" if value is None else str(value)
