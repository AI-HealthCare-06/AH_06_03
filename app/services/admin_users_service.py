"""관리자: 가입자 목록·상세, 테스트 계정 일괄 삭제.

건강 수치(혈압·몸무게 등)와 일기·사진은 읽지도 돌려주지도 않는다. 조회·삭제는 서버 로그에 남긴다.
"""
import logging
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.models.challenge import ChallengeCycle
from app.models.consent import ConsentPolicy, UserConsent
from app.models.eligibility import EligibilityAssessment
from app.models.health import HealthRecord
from app.models.prediction import PredictionJob
from app.models.survey import SurveyInstance
from app.models.user import User
from app.schemas.admin import (
    AdminConsentItem, AdminUserDetail, AdminUserList, AdminUserRow, PurgeResult, PurgeTarget,
)
from app.services import account_service, audit_service

logger = logging.getLogger(__name__)

STAGES = ["signup", "eligibility", "health", "survey", "prediction", "challenge"]
STAGE_TABLES = {          # 단계 → 그 단계를 마쳤다는 증거가 되는 표 (user_id 칸이 있는 것)
    "eligibility": EligibilityAssessment, "health": HealthRecord, "survey": SurveyInstance,
    "prediction": PredictionJob, "challenge": ChallengeCycle,
}


def mask_email(email: str) -> str:
    if email.startswith("deleted+"):
        return "(탈퇴한 계정)"
    local, _, domain = email.partition("@")
    keep = 1 if len(local) <= 2 else 2   # 아주 짧은 주소는 한 글자만 보인다
    return f"{local[:keep]}{'*' * (len(local) - keep)}@{domain}"


def _iso(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


VIEW = audit_service.VIEW_DEDUPE_SECONDS   # 같은 화면을 새로고침해도 기록이 쌓이지 않게 한동안 한 번만


async def _stages(db: AsyncSession, user_ids: list[str]) -> dict[str, set[str]]:
    done: dict[str, set[str]] = {uid: {"signup"} for uid in user_ids}
    if not user_ids:
        return done
    for stage, model in STAGE_TABLES.items():
        for (uid,) in (await db.execute(select(model.user_id).where(model.user_id.in_(user_ids)).distinct())).all():
            done[uid].add(stage)
    return done


async def _health_consent(db: AsyncSession, user_ids: list[str]) -> dict[str, str]:
    """건강정보 동의의 가장 최근 상태. 기록이 없으면 'none'."""
    out = {uid: "none" for uid in user_ids}
    if not user_ids:
        return out
    rows = (await db.execute(
        select(UserConsent.user_id, UserConsent.status)
        .join(ConsentPolicy, ConsentPolicy.policy_id == UserConsent.policy_id)
        .where(ConsentPolicy.policy_type == "health_data", UserConsent.user_id.in_(user_ids))
        .order_by(UserConsent.consented_at)
    )).all()
    for uid, status in rows:      # 시각 순이라 마지막 값이 최신
        out[uid] = status
    return out


def _row(user: User, stages: set[str], consent: str) -> AdminUserRow:
    return AdminUserRow(
        user_id_short=user.user_id[-8:], user_id=user.user_id, email_masked=mask_email(user.email), status=user.status,
        joined_at=_iso(user.created_at) or "", stage=max(stages, key=STAGES.index), health_consent=consent,
    )


async def list_users(
    db: AsyncSession, admin: str, q: str | None, stage: str | None, consent: str | None, status: str | None,
    limit: int, offset: int,
) -> AdminUserList:
    cond = []
    if q:
        cond.append(User.email.ilike(f"%{q.strip()}%"))
    if status in ("active", "deleted"):
        cond.append(User.status == status)
    users = (await db.execute(select(User).where(*cond).order_by(User.created_at.desc(), User.email))).scalars().all()
    ids = [u.user_id for u in users]
    stages, consents = await _stages(db, ids), await _health_consent(db, ids)
    rows = [_row(u, stages[u.user_id], consents[u.user_id]) for u in users]
    if stage in STAGES:
        rows = [r for r in rows if r.stage == stage]
    if consent in ("agreed", "withdrawn", "none"):
        rows = [r for r in rows if r.health_consent == consent]
    await audit_service.record(db, admin, "users_view", dedupe_seconds=VIEW)
    await db.commit()
    return AdminUserList(total=len(rows), items=rows[offset:offset + limit])


async def user_detail(db: AsyncSession, admin: str, user_id: str) -> AdminUserDetail:
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(404, "ADMIN_USER_NOT_FOUND", "가입자를 찾을 수 없습니다.")
    stages = (await _stages(db, [user_id]))[user_id]
    consent = (await _health_consent(db, [user_id]))[user_id]
    consents = (await db.execute(
        select(ConsentPolicy.policy_type, ConsentPolicy.version, UserConsent.status, UserConsent.consented_at, UserConsent.withdrawn_at)
        .join(UserConsent, UserConsent.policy_id == ConsentPolicy.policy_id)
        .where(UserConsent.user_id == user_id).order_by(UserConsent.consented_at)
    )).all()
    cycles = (await db.execute(select(func.count()).select_from(ChallengeCycle).where(ChallengeCycle.user_id == user_id))).scalar_one()
    base = _row(user, stages, consent)
    await audit_service.record(db, admin, "user_detail_view", target=user.user_id[-8:])
    await db.commit()
    return AdminUserDetail(
        **base.model_dump(), stages_done=[s for s in STAGES if s in stages], cycles=int(cycles),
        consents=[
            AdminConsentItem(policy_type=t, version=v, status=s, consented_at=_iso(c) or "", withdrawn_at=_iso(w))
            for t, v, s, c, w in consents
        ],
    )


def _check_patterns(patterns: list[str]) -> None:
    for p in patterns:
        if "@" not in p or p.replace("%", "").replace("_", "") in {"", "@"}:
            raise AppError(422, "ADMIN_PATTERN_TOO_WIDE", f"너무 넓은 패턴이에요: {p} (예: %@a.com)")


async def purge(db: AsyncSession, admin: str, patterns: list[str], apply: bool, confirm_count: int | None) -> PurgeResult:
    """미리보기(apply=False) 또는 실제 탈퇴 처리. 실제로 지울 때는 미리보기에서 본 인원수를 confirm_count로 다시 보내야 한다.
    관리자 계정은 대상에서 뺀다."""
    _check_patterns(patterns)
    found = (await db.execute(
        select(User).where(User.status != "deleted").where(or_(*[User.email.ilike(p) for p in patterns])).order_by(User.email)
    )).scalars().all()
    users = [u for u in found if u.email.lower() not in settings.admin_email_set]
    targets = [PurgeTarget(email_masked=mask_email(u.email), status=u.status) for u in users]
    if not apply:
        await audit_service.record(db, admin, "purge_preview", detail=f"패턴 {len(patterns)}개, 대상 {len(users)}명")
        await db.commit()
        return PurgeResult(count=len(users), targets=targets, applied=False)
    if confirm_count != len(users):
        raise AppError(409, "ADMIN_PURGE_CONFIRM", f"미리보기와 인원수가 달라요(지금 {len(users)}명). 다시 미리보기를 해 주세요.")
    ids = [u.user_id for u in users]
    done, failed = 0, 0
    for user_id in ids:
        try:
            user = await db.get(User, user_id, populate_existing=True)
            await account_service.delete_account_data(db, user)
            await db.commit()
            done += 1
        except Exception:    # 한 명이 실패해도 나머지는 계속
            await db.rollback()
            failed += 1
            logger.exception("일괄 삭제 실패: %s", user_id[-8:])
    await audit_service.record(db, admin, "purge_apply", detail=f"대상 {len(ids)}명, 완료 {done}명, 실패 {failed}명")
    await db.commit()
    return PurgeResult(count=len(ids), targets=targets, applied=True, done=done, failed=failed)
