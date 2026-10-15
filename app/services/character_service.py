"""캐릭터 꾸미기: 아이템 목록, 구매(보유 기록 + 파이 차감), 조합 저장·조회.
가격은 character_catalog가 기준이다. 화면이 보낸 가격은 믿지 않는다."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.character import CharacterItem, UserCharacter
from app.models.community import CommunityProfile
from app.models.user import User
from app.schemas.character import CharacterView, ItemsResult, ItemView, SlotView
from app.services import pie_service
from app.services.character_catalog import DEFAULT, ITEMS, PRICE, SLOTS, item_key

SHOP_BUY = "shop_buy"   # 파이 장부의 이유 이름


async def _owned(db: AsyncSession, user_id: str) -> set[str]:
    return set((await db.execute(
        select(CharacterItem.item_key).where(CharacterItem.user_id == user_id)
    )).scalars().all())


async def list_items(db: AsyncSession, user_id: str) -> ItemsResult:
    """아이템 전체 + 보유 여부 + 내 파이 잔액."""
    owned = await _owned(db, user_id)
    slots = [
        SlotView(slot=slot, items=[
            ItemView(key=key, label=label, price=price, owned=price == 0 or item_key(slot, key) in owned)
            for key, label, price in ITEMS[slot]
        ])
        for slot in SLOTS
    ]
    return ItemsResult(balance=await pie_service.balance(db, user_id), slots=slots)


async def buy(db: AsyncSession, user_id: str, key: str) -> ItemsResult:
    """아이템 구매: 보유 기록 + 파이 차감을 한 번에 저장한다."""
    if key not in PRICE:
        raise AppError(422, "CHARACTER_ITEM_UNKNOWN", "없는 아이템이에요.")
    price = PRICE[key]
    if price == 0:
        raise AppError(422, "CHARACTER_ITEM_FREE", "기본 아이템은 사지 않아도 쓸 수 있어요.")

    # 같은 사람의 구매를 한 번에 하나씩 처리한다 (다른 아이템 두 개를 동시에 사서 잔액이 마이너스가 되지 않게)
    await db.execute(select(User.user_id).where(User.user_id == user_id).with_for_update())

    if key in await _owned(db, user_id):
        raise AppError(409, "CHARACTER_ITEM_OWNED", "이미 가지고 있는 아이템이에요.")
    if await pie_service.balance(db, user_id) < price:
        raise AppError(409, "PIE_NOT_ENOUGH", "파이가 모자라요.")

    try:
        db.add(CharacterItem(user_id=user_id, item_key=key, acquired_at=utcnow()))
        await db.flush()
        if not await pie_service.add(db, user_id, -price, SHOP_BUY, key):
            raise IntegrityError(None, None, Exception("이미 차감됨"))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "CHARACTER_ITEM_OWNED", "이미 가지고 있는 아이템이에요.")
    return await list_items(db, user_id)


async def get_me(db: AsyncSession, user_id: str) -> CharacterView:
    """내 조합. 저장한 적이 없으면 기본 모습."""
    row = await db.get(UserCharacter, user_id)
    return CharacterView(**({s: getattr(row, s) for s in SLOTS} if row else DEFAULT))


async def save_me(db: AsyncSession, user_id: str, combo: dict) -> CharacterView:
    """조합 저장. 각 칸은 무료이거나 산 아이템이어야 한다."""
    owned = await _owned(db, user_id)
    for slot in SLOTS:
        k = item_key(slot, combo[slot])
        if k not in PRICE:
            raise AppError(422, "CHARACTER_ITEM_UNKNOWN", f"{slot}: 없는 아이템이에요.")
        if PRICE[k] > 0 and k not in owned:
            raise AppError(409, "CHARACTER_ITEM_NOT_OWNED", f"{slot}: 아직 사지 않은 아이템이에요.")

    row = await db.get(UserCharacter, user_id)
    if row is None:
        row = UserCharacter(user_id=user_id, **{s: combo[s] for s in SLOTS}, updated_at=utcnow())
        db.add(row)
    else:
        for s in SLOTS:
            setattr(row, s, combo[s])
        row.updated_at = utcnow()
    await db.commit()
    return CharacterView(**{s: combo[s] for s in SLOTS})


async def characters_for(db: AsyncSession, user_ids: list[str]) -> dict[str, CharacterView]:
    """여러 사람의 조합을 한 번에 (커뮤니티 글·댓글, 파티원 목록용). 저장 안 한 사람은 기본 모습."""
    ids = list(set(user_ids))
    if not ids:
        return {}
    rows = (await db.execute(select(UserCharacter).where(UserCharacter.user_id.in_(ids)))).scalars().all()
    found = {r.user_id: CharacterView(**{s: getattr(r, s) for s in SLOTS}) for r in rows}
    return {uid: found.get(uid, CharacterView(**DEFAULT)) for uid in ids}


async def by_nickname(db: AsyncSession, nickname: str) -> CharacterView:
    """닉네임으로 조합 찾기 (프로필 화면용)."""
    uid = (await db.execute(
        select(CommunityProfile.user_id).where(CommunityProfile.nickname == nickname)
    )).scalar_one_or_none()
    if uid is None:
        raise AppError(404, "COMMUNITY_PROFILE_NOT_FOUND", "그런 닉네임이 없어요.")
    return (await characters_for(db, [uid]))[uid]