"""파티: 만들기, 초대 코드로 참여, 나가기.
- 파티는 선택 미션 8개 중 하나를 함께 인증한다 (흡연·음주 고정 미션은 파티원에게 공개하기 부적절해서 제외)
- 최대 6명, 한 사람에 한 파티 (party_members.user_id 유니크)
- 파티장은 가장 먼저 들어온 파티원 (따로 저장하지 않는다)"""
import secrets

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.challenge import Challenge
from app.models.party import MAX_MEMBERS, Party, PartyCheckin, PartyMember
from app.schemas.party import PartyChallengeOption, PartyInfo
from app.services.challenge_service import today_kst

CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # 헷갈리는 0·O·1·I는 뺐다


def _new_code() -> str:
    return "PAEON-" + "".join(secrets.choice(CODE_CHARS) for _ in range(4))


async def challenge_options(db: AsyncSession) -> list[PartyChallengeOption]:
    """파티 챌린지 후보: 선택 미션(mission_role=selectable) 중 사용 중인 것."""
    rows = (await db.execute(
        select(Challenge.challenge_code, Challenge.challenge_name)
        .where(Challenge.mission_role == "selectable", Challenge.active.is_(True))
        .order_by(Challenge.challenge_code)
    )).all()
    return [PartyChallengeOption(challenge_code=c, challenge_name=n) for c, n in rows]


async def _membership(db: AsyncSession, user_id: str) -> PartyMember | None:
    return (await db.execute(select(PartyMember).where(PartyMember.user_id == user_id))).scalar_one_or_none()


async def _info(db: AsyncSession, party: Party) -> PartyInfo:
    count = (await db.execute(
        select(func.count()).select_from(PartyMember).where(PartyMember.party_id == party.party_id)
    )).scalar_one()
    name = (await db.execute(
        select(Challenge.challenge_name).where(Challenge.challenge_code == party.challenge_code)
    )).scalar_one_or_none() or party.challenge_code
    return PartyInfo(party_id=party.party_id, name=party.name, intro=party.intro, invite_code=party.invite_code,
                     challenge_code=party.challenge_code, challenge_name=name, started_on=party.started_on,
                     member_count=count, max_members=MAX_MEMBERS)


async def create(db: AsyncSession, user_id: str, name: str, intro: str | None, challenge_code: str) -> PartyInfo:
    name = name.strip()
    if not 2 <= len(name) <= 12:
        raise AppError(422, "PARTY_NAME_INVALID", "파티 이름은 2~12자로 지어 주세요.")
    if challenge_code not in {o.challenge_code for o in await challenge_options(db)}:
        raise AppError(422, "PARTY_CHALLENGE_INVALID", "파티에서 고를 수 없는 챌린지예요.")
    if await _membership(db, user_id) is not None:
        raise AppError(409, "PARTY_ALREADY_JOINED", "이미 파티에 들어가 있어요.")

    today, now = today_kst(), utcnow()
    for _ in range(5):                                   # 초대 코드가 우연히 겹치면 다시 만든다
        party = Party(name=name, intro=(intro or "").strip() or None, invite_code=_new_code(),
                      challenge_code=challenge_code, started_on=today, created_at=now)
        try:
            async with db.begin_nested():
                db.add(party)
                await db.flush()
            break
        except IntegrityError:
            continue
    else:
        raise AppError(500, "PARTY_CODE_FAILED", "잠시 후 다시 시도해 주세요.")

    try:
        db.add(PartyMember(party_id=party.party_id, user_id=user_id, joined_at=now, joined_on=today))
        await db.commit()
    except IntegrityError:                               # 동시에 다른 파티에 들어간 경우
        await db.rollback()
        raise AppError(409, "PARTY_ALREADY_JOINED", "이미 파티에 들어가 있어요.")
    return await _info(db, party)


async def join(db: AsyncSession, user_id: str, invite_code: str) -> PartyInfo:
    code = invite_code.strip().upper()
    party = (await db.execute(
        select(Party).where(Party.invite_code == code).with_for_update()   # 같은 파티 참여를 한 번에 하나씩 (7번째 막기)
    )).scalar_one_or_none()
    if party is None:
        raise AppError(404, "PARTY_NOT_FOUND", "초대 코드를 다시 확인해 주세요.")
    if await _membership(db, user_id) is not None:
        raise AppError(409, "PARTY_ALREADY_JOINED", "이미 파티에 들어가 있어요.")
    count = (await db.execute(
        select(func.count()).select_from(PartyMember).where(PartyMember.party_id == party.party_id)
    )).scalar_one()
    if count >= MAX_MEMBERS:
        raise AppError(409, "PARTY_FULL", "파티 자리가 다 찼어요.")
    try:
        db.add(PartyMember(party_id=party.party_id, user_id=user_id, joined_at=utcnow(), joined_on=today_kst()))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "PARTY_ALREADY_JOINED", "이미 파티에 들어가 있어요.")
    return await _info(db, party)


async def leave(db: AsyncSession, user_id: str) -> None:
    """나가기. 그 사람의 파티 인증도 지운다. 마지막 한 명이 나가면 파티를 지운다."""
    m = await _membership(db, user_id)
    if m is None:
        raise AppError(404, "PARTY_NOT_JOINED", "들어가 있는 파티가 없어요.")
    party_id = m.party_id
    await db.execute(delete(PartyCheckin).where(PartyCheckin.party_id == party_id, PartyCheckin.user_id == user_id))
    await db.delete(m)
    await db.flush()
    left = (await db.execute(
        select(func.count()).select_from(PartyMember).where(PartyMember.party_id == party_id)
    )).scalar_one()
    if left == 0:
        await db.execute(delete(Party).where(Party.party_id == party_id))
    await db.commit()


async def is_member(db: AsyncSession, user_id: str, party_id: str) -> bool:
    """이 사람이 이 파티 소속인가 (파티 글 쓰기·보기 확인용)."""
    m = await _membership(db, user_id)
    return m is not None and m.party_id == party_id