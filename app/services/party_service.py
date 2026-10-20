"""파티: 만들기, 초대 코드로 참여, 나가기.
- 파티는 선택 미션 8개 중 하나를 함께 인증한다 (흡연·음주 고정 미션은 파티원에게 공개하기 부적절해서 제외)
- 최대 6명, 한 사람에 한 파티 (party_members.user_id 유니크)
- 파티장은 가장 먼저 들어온 파티원 (따로 저장하지 않는다)"""
import secrets
from collections import deque
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.challenge import Challenge
from app.models.community import CommunityComment, CommunityLike, CommunityPost, CommunityPostPhoto, CommunityProfile, CommunityReport
from app.models.party import MAX_MEMBERS, Party, PartyCheckin, PartyMember
from app.schemas.party import PartyCard, PartyChallengeOption, PartyHome, PartyInfo, PartyMemberView
from app.services import character_service, pie_service
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


# 초대 코드 대입 막기: 코드가 4글자(약 100만 가지)라, 한 사람이 1시간에 10번 틀리면 잠시 막는다(API 보안 검사 4묶음).
# 횟수는 메모리에만 둔다(로그인 시도 제한과 같은 방식, uvicorn 1개라 충분, 재배포하면 0).
JOIN_FAIL_WINDOW = timedelta(hours=1)
JOIN_FAIL_MAX = 10
_join_failures: dict[str, deque[datetime]] = {}


def _recent_join_failures(user_id: str, now: datetime) -> int:
    q = _join_failures.get(user_id)
    while q and q[0] <= now - JOIN_FAIL_WINDOW:
        q.popleft()
    if q is not None and not q:
        del _join_failures[user_id]
        return 0
    return len(q) if q else 0


async def join(db: AsyncSession, user_id: str, invite_code: str) -> PartyInfo:
    now = utcnow()
    if _recent_join_failures(user_id, now) >= JOIN_FAIL_MAX:
        raise AppError(429, "PARTY_JOIN_TOO_MANY", "초대 코드를 여러 번 틀려서 잠시 막혔어요. 한 시간 뒤에 다시 시도해 주세요.")
    code = invite_code.strip().upper()
    party = (await db.execute(
        select(Party).where(Party.invite_code == code).with_for_update()   # 같은 파티 참여를 한 번에 하나씩 (7번째 막기)
    )).scalar_one_or_none()
    if party is None:
        _join_failures.setdefault(user_id, deque()).append(now)
        raise AppError(404, "PARTY_NOT_FOUND", "초대 코드를 다시 확인해 주세요.")
    _join_failures.pop(user_id, None)
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
        # 파티가 없어지면 파티 글과 거기 딸린 좋아요·댓글·신고도 지운다 (DB의 CASCADE와 같은 결과, 테스트 DB에서도 같게)
        post_ids = select(CommunityPost.post_id).where(CommunityPost.party_id == party_id)
        comment_ids = select(CommunityComment.comment_id).where(CommunityComment.post_id.in_(post_ids))
        await db.execute(delete(CommunityReport).where(
            (CommunityReport.post_id.in_(post_ids)) | (CommunityReport.comment_id.in_(comment_ids))))
        await db.execute(delete(CommunityLike).where(CommunityLike.post_id.in_(post_ids)))
        await db.execute(delete(CommunityComment).where(CommunityComment.post_id.in_(post_ids)))
        await db.execute(delete(CommunityPostPhoto).where(CommunityPostPhoto.post_id.in_(post_ids)))
        await db.execute(delete(CommunityPost).where(CommunityPost.party_id == party_id))
        await db.execute(delete(Party).where(Party.party_id == party_id))
    await db.commit()


async def is_member(db: AsyncSession, user_id: str, party_id: str) -> bool:
    """이 사람이 이 파티 소속인가 (파티 글 쓰기·보기 확인용)."""
    m = await _membership(db, user_id)
    return m is not None and m.party_id == party_id

# ---------------------------------------------------------------- 파티 현황 · 인증
ALL_CHECKIN = "party_all_checkin"   # 파이 장부 이유: 파티 전원 인증
ALL_CHECKIN_PIE = 3


async def _members(db: AsyncSession, party_id: str) -> list[PartyMember]:
    """들어온 순서대로 (첫 번째가 파티장)."""
    return list((await db.execute(
        select(PartyMember).where(PartyMember.party_id == party_id)
        .order_by(PartyMember.joined_at, PartyMember.party_member_id)
    )).scalars().all())


async def _checkins(db: AsyncSession, party_id: str) -> dict[str, set]:
    """파티원 → 인증한 날짜들."""
    rows = (await db.execute(
        select(PartyCheckin.user_id, PartyCheckin.checkin_date).where(PartyCheckin.party_id == party_id)
    )).all()
    out: dict[str, set] = {}
    for uid, d in rows:
        out.setdefault(uid, set()).add(d)
    return out


def _all_done(members: list[PartyMember], checkins: dict[str, set], day) -> bool:
    """그날 이미 들어와 있던 파티원이 모두 인증했나 (그날 이후에 들어온 사람은 빼고 본다)."""
    present = [m for m in members if m.joined_on <= day]
    return bool(present) and all(day in checkins.get(m.user_id, set()) for m in present)


def _party_streak(members, checkins, today) -> int:
    """모두 인증한 날이 오늘(오늘 아직이면 어제)까지 이어진 일수."""
    cur = today if _all_done(members, checkins, today) else today - timedelta(days=1)
    n = 0
    while _all_done(members, checkins, cur):
        n += 1
        cur -= timedelta(days=1)
    return n


async def home(db: AsyncSession, user_id: str) -> PartyHome:
    """파티 현황: 파티원별 오늘 완료·N일 중 M일, 파티 연속 인증."""
    m = await _membership(db, user_id)
    if m is None:
        raise AppError(404, "PARTY_NOT_JOINED", "들어가 있는 파티가 없어요.")
    party = await db.get(Party, m.party_id)
    today = today_kst()
    members = await _members(db, party.party_id)
    checkins = await _checkins(db, party.party_id)
    ids = [x.user_id for x in members]
    nicks = dict((await db.execute(
        select(CommunityProfile.user_id, CommunityProfile.nickname).where(CommunityProfile.user_id.in_(ids))
    )).all())
    chars = await character_service.characters_for(db, ids)

    views = []
    for i, x in enumerate(members):
        days = checkins.get(x.user_id, set())
        views.append(PartyMemberView(
            nickname=nicks.get(x.user_id, "파티원"), character=chars[x.user_id].model_dump(),
            is_leader=i == 0, is_me=x.user_id == user_id, done_today=today in days,
            days_total=(today - x.joined_on).days + 1,
            days_done=sum(1 for d in days if x.joined_on <= d <= today),
        ))
    remaining = sum(1 for v in views if not v.done_today)
    return PartyHome(party=await _info(db, party), day_number=(today - party.started_on).days + 1,
                     members=views, streak=_party_streak(members, checkins, today),
                     today_all_done=remaining == 0, today_remaining=remaining)


async def checkin(db: AsyncSession, user_id: str) -> PartyHome:
    """오늘 파티 챌린지 '완료'. 하루 한 번. 마지막 파티원이 인증하면 모두에게 +3 파이."""
    m = await _membership(db, user_id)
    if m is None:
        raise AppError(404, "PARTY_NOT_JOINED", "들어가 있는 파티가 없어요.")
    today = today_kst()
    try:
        async with db.begin_nested():
            db.add(PartyCheckin(party_id=m.party_id, user_id=user_id, checkin_date=today, created_at=utcnow()))
            await db.flush()
    except IntegrityError:
        pass                                             # 오늘 이미 인증함 (두 번 눌러도 한 번)

    members = await _members(db, m.party_id)
    if _all_done(members, await _checkins(db, m.party_id), today):
        for x in members:
            await pie_service.add(db, x.user_id, ALL_CHECKIN_PIE, ALL_CHECKIN, f"{m.party_id}:{today.isoformat()}")
    await db.commit()
    return await home(db, user_id)


async def card(db: AsyncSession, party_id: str) -> PartyCard:
    """파티 글에 붙는 카드: 파티 이름 + 파티 연속 인증 일수."""
    party = await db.get(Party, party_id)
    if party is None:
        raise AppError(404, "PARTY_NOT_FOUND", "파티를 찾을 수 없어요.")
    members = await _members(db, party_id)
    return PartyCard(name=party.name, streak=_party_streak(members, await _checkins(db, party_id), today_kst()))

async def my_party_id(db: AsyncSession, user_id: str) -> str:
    """파티 글을 쓰거나 볼 때 쓰는 내 파티 번호. 파티가 없으면 PARTY_NOT_JOINED."""
    m = await _membership(db, user_id)
    if m is None:
        raise AppError(404, "PARTY_NOT_JOINED", "들어가 있는 파티가 없어요.")
    return m.party_id
