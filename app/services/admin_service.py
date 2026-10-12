"""관리자 최소 기능: 챌린지 카테고리·미션의 노출(active)과 카테고리 순서(display_order)를 바꾼다.

이미 있는 칸만 바꾸고 새 표·칸은 만들지 않는다. 값은 요청마다 DB에서 읽히므로 바로 반영된다.
노출 스위치는 '선택 미션 후보'에만 적용된다 (고정 미션과 대체 미션은 추천 규칙이 정한다).
"""
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.challenge import Challenge, ChallengeCategory
from app.schemas.admin import AdminCategory, AdminMission

logger = logging.getLogger(__name__)

SWITCHABLE_ROLE = "selectable"


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
    await db.commit()
    logger.info("관리자 %s: 카테고리 %s 노출=%s 순서=%s", admin_email, cat.category_code, result.active, result.display_order)
    return result


async def update_mission(db: AsyncSession, challenge_id: str, active: bool, admin_email: str) -> AdminMission:
    ch = await db.get(Challenge, challenge_id)
    if ch is None:
        raise AppError(404, "ADMIN_MISSION_NOT_FOUND", "미션을 찾을 수 없습니다.")
    if ch.mission_role != SWITCHABLE_ROLE and active != bool(ch.active):
        raise AppError(422, "ADMIN_NOT_SWITCHABLE", "고정·대체 미션은 추천 규칙이 정해서 노출을 바꿀 수 없습니다.")
    ch.active = active
    await db.flush()
    if await _selectable_active_count(db) == 0:
        await db.rollback()
        raise AppError(409, "ADMIN_LAST_SELECTABLE", "선택할 수 있는 미션이 하나도 남지 않아 바꿀 수 없습니다.")
    result = _mission(ch)
    await db.commit()
    logger.info("관리자 %s: 미션 %s 노출=%s", admin_email, ch.challenge_code, result.active)
    return result
