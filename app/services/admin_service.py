"""관리자 최소 기능: 챌린지 카테고리·미션의 노출(active)과 카테고리 순서(display_order)를 바꾼다.

이미 있는 칸만 바꾸고 새 표·칸은 만들지 않는다. 값은 요청마다 DB에서 읽히므로 바로 반영된다.
노출 스위치는 '선택 미션 후보'에만 적용된다 (고정 미션과 대체 미션은 추천 규칙이 정한다).
"""
import logging

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.challenge import Challenge, ChallengeCategory, ChallengeCycle, ChallengeLog, CycleChallenge
from app.services import audit_service
from app.schemas.admin import AdminCategory, AdminMission, ChallengeStats, CycleStat, MissionStat

logger = logging.getLogger(__name__)

SWITCHABLE_ROLE = "selectable"


def _onoff(value: bool) -> str:
    return "켬" if value else "끔"


def _mission(ch: Challenge) -> AdminMission:
    return AdminMission(
        challenge_id=ch.challenge_id, challenge_code=ch.challenge_code, challenge_name=ch.challenge_name,
        mission_role=ch.mission_role, active=bool(ch.active), switchable=ch.mission_role == SWITCHABLE_ROLE,
    )


def _category(cat: ChallengeCategory, missions: list[Challenge]) -> AdminCategory:
    items = [_mission(m) for m in missions]
    return AdminCategory(
        category_id=cat.category_id, category_code=cat.category_code, category_name=cat.category_name,
        display_order=cat.display_order, active=bool(cat.active),
        switchable=any(m.switchable for m in items), missions=items,
    )


async def _missions_of(db: AsyncSession, category_id: str) -> list[Challenge]:
    rows = await db.execute(
        select(Challenge).where(Challenge.category_id == category_id).order_by(Challenge.challenge_code)
    )
    return list(rows.scalars().all())


async def _selectable_active_count(db: AsyncSession) -> int:
    """지금 노출 중인 선택 미션 수 (카테고리와 미션이 둘 다 켜진 것)."""
    result = await db.execute(
        select(func.count()).select_from(Challenge)
        .join(ChallengeCategory, ChallengeCategory.category_id == Challenge.category_id)
        .where(Challenge.mission_role == SWITCHABLE_ROLE, Challenge.active.is_(True), ChallengeCategory.active.is_(True))
    )
    return int(result.scalar_one())


async def list_catalog(db: AsyncSession) -> list[AdminCategory]:
    cats = (await db.execute(
        select(ChallengeCategory).order_by(ChallengeCategory.display_order, ChallengeCategory.category_code)
    )).scalars().all()
    missions = (await db.execute(select(Challenge).order_by(Challenge.challenge_code))).scalars().all()
    by_cat: dict[str, list[Challenge]] = {}
    for m in missions:
        by_cat.setdefault(m.category_id, []).append(m)
    return [_category(c, by_cat.get(c.category_id, [])) for c in cats]


async def update_category(
    db: AsyncSession, category_id: str, active: bool | None, display_order: int | None, admin_email: str
) -> AdminCategory:
    cat = await db.get(ChallengeCategory, category_id)
    if cat is None:
        raise AppError(404, "ADMIN_CATEGORY_NOT_FOUND", "카테고리를 찾을 수 없습니다.")
    missions = await _missions_of(db, category_id)
    old_active, old_order, changes = bool(cat.active), cat.display_order, []
    if active is not None and active != bool(cat.active):
        if not any(m.mission_role == SWITCHABLE_ROLE for m in missions):
            raise AppError(422, "ADMIN_NOT_SWITCHABLE", "고정 미션만 있는 카테고리는 노출을 바꿀 수 없습니다.")
        cat.active = active
    if display_order is not None:
        cat.display_order = display_order
    await db.flush()
    if await _selectable_active_count(db) == 0:
        await db.rollback()
        raise AppError(409, "ADMIN_LAST_SELECTABLE", "선택할 수 있는 미션이 하나도 남지 않아 바꿀 수 없습니다.")
    result = _category(cat, missions)
    if result.active != old_active:
        changes.append(f"노출 {_onoff(old_active)}→{_onoff(result.active)}")
    if result.display_order != old_order:
        changes.append(f"순서 {old_order}→{result.display_order}")
    if changes:
        await audit_service.record(db, admin_email, "category_update", cat.category_code, ", ".join(changes))
    await db.commit()
    logger.info("관리자 변경: 카테고리 %s 노출=%s 순서=%s", cat.category_code, result.active, result.display_order)  # 누가 했는지는 admin_audit_logs에 남는다
    return result


async def update_mission(db: AsyncSession, challenge_id: str, active: bool, admin_email: str) -> AdminMission:
    ch = await db.get(Challenge, challenge_id)
    if ch is None:
        raise AppError(404, "ADMIN_MISSION_NOT_FOUND", "미션을 찾을 수 없습니다.")
    if ch.mission_role != SWITCHABLE_ROLE and active != bool(ch.active):
        raise AppError(422, "ADMIN_NOT_SWITCHABLE", "고정·대체 미션은 추천 규칙이 정해서 노출을 바꿀 수 없습니다.")
    old_active = bool(ch.active)
    ch.active = active
    await db.flush()
    if await _selectable_active_count(db) == 0:
        await db.rollback()
        raise AppError(409, "ADMIN_LAST_SELECTABLE", "선택할 수 있는 미션이 하나도 남지 않아 바꿀 수 없습니다.")
    result = _mission(ch)
    if result.active != old_active:
        await audit_service.record(db, admin_email, "mission_update", ch.challenge_code,
                                   f"노출 {_onoff(old_active)}→{_onoff(result.active)}")
    await db.commit()
    logger.info("관리자 변경: 미션 %s 노출=%s", ch.challenge_code, result.active)
    return result


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def _mean(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


async def challenge_stats(db: AsyncSession) -> ChallengeStats:
    """미션별·사이클별 통계. 이미 있는 기록을 세기만 하고, 사용자를 알아볼 수 있는 값은 내보내지 않는다.
    탈퇴한 사용자의 기록은 탈퇴 때 지워져서 자연히 빠진다."""
    catalog = (await db.execute(
        select(Challenge, ChallengeCategory)
        .join(ChallengeCategory, ChallengeCategory.category_id == Challenge.category_id)
        .order_by(ChallengeCategory.display_order, Challenge.challenge_code)
    )).all()

    logged = func.count(ChallengeLog.challenge_log_id)
    done = func.coalesce(func.sum(case((ChallengeLog.status == "completed", 1), else_=0)), 0)
    rows = (await db.execute(
        select(Challenge.challenge_code, CycleChallenge.selection_type, CycleChallenge.status, logged, done)
        .select_from(CycleChallenge)
        .join(ChallengeCycle, ChallengeCycle.cycle_id == CycleChallenge.cycle_id)  # 사이클이 남아 있는 기록만
        .join(Challenge, Challenge.challenge_id == CycleChallenge.challenge_id)
        .outerjoin(ChallengeLog, ChallengeLog.cycle_challenge_id == CycleChallenge.cycle_challenge_id)
        .group_by(CycleChallenge.cycle_challenge_id, Challenge.challenge_code, CycleChallenge.selection_type, CycleChallenge.status)
    )).all()
    by_code: dict[str, list] = {}
    for code, selection_type, status, n_logged, n_done in rows:
        by_code.setdefault(code, []).append((selection_type, status, int(n_logged), int(n_done)))

    missions = []
    for ch, cat in catalog:
        items = by_code.get(ch.challenge_code, [])
        count = lambda st: sum(1 for _, status, _, _ in items if status == st)  # noqa: E731
        completed, incomplete, stopped = count("completed"), count("incomplete"), count("stopped")
        missions.append(MissionStat(
            challenge_code=ch.challenge_code, challenge_name=ch.challenge_name, category_name=cat.category_name,
            mission_role=ch.mission_role, assigned_count=len(items),
            selected_count=sum(1 for t, _, _, _ in items if t == "selected"),
            active_count=count("active"), completed_count=completed, incomplete_count=incomplete, stopped_count=stopped,
            completion_rate=_rate(completed, completed + incomplete),
            giving_up_rate=_rate(stopped, completed + incomplete + stopped),
            avg_logged_days=_mean([n for _, _, n, _ in items]), avg_completed_days=_mean([d for _, _, _, d in items]),
        ))

    cyc = dict((await db.execute(select(ChallengeCycle.status, func.count()).group_by(ChallengeCycle.status))).all())
    users_started = int((await db.execute(select(func.count(func.distinct(ChallengeCycle.user_id))))).scalar_one())
    a, c, i, s_ = (int(cyc.get(k, 0)) for k in ("active", "completed", "incomplete", "stopped"))
    cycles = CycleStat(total=a + c + i + s_, active=a, completed=c, incomplete=i, stopped=s_,
                       completion_rate=_rate(c, c + i), giving_up_rate=_rate(s_, c + i + s_), users_started=users_started)
    return ChallengeStats(missions=missions, cycles=cycles)
