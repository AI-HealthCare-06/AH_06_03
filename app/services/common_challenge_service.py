"""공통 챌린지: 운영팀이 기간을 정해 열면 이용자가 참여해 하루 한 번 인증하고, 인증한 일수로 순위를 매긴다.

- 순위: 인증 일수가 많은 순 → 같으면 그 일수에 먼저 도달한 사람(마지막 인증 시각이 빠른 쪽) → 그래도 같으면 회원 번호.
- 보상: 끝난 뒤 관리자가 "순위 확정"을 누르면 1·2·3위에게 순위 보상, 그 밖에 인증 일수가 완주 기준 이상인 사람에게 완주 보상을
  파이 장부에 적립한다. 한 번만 가능하고, 순위 보상을 받은 사람은 완주 보상을 따로 받지 않는다.
- 건강 수치는 비교하지 않는다. 걸음 수는 인증을 인정할지 가리는 데만 쓰고, 순위·목록에는 내보내지 않는다.
"""
import math
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.common_challenge import CommonChallenge, CommonChallengeCert, CommonChallengeParticipant
from app.models.community import CommunityProfile
from app.schemas.common_challenge import (
    AdminChallengeItem, AdminChallengeList, CertifyRequest, CertifyResult, ChallengeCreate, ChallengePatch,
    CommonChallengeDetail, CommonChallengeItem, CommonChallengeList, FinalizeResult, JoinResult, RankRow, Rewards,
)
from app.services import audit_service, community_service, pie_service
from app.services.challenge_service import today_kst

TOP_N = 5
DEFAULT_COMPLETE_RATE = 0.7


def _not_found() -> AppError:
    return AppError(404, "COMMON_CHALLENGE_NOT_FOUND", "챌린지를 찾을 수 없어요.")


def state_of(c: CommonChallenge, today: date) -> str:
    if today < c.starts_on:
        return "upcoming"
    if today > c.ends_on:
        return "ended"
    return "active"


def total_days(c: CommonChallenge) -> int:
    return (c.ends_on - c.starts_on).days + 1


def _rewards(c: CommonChallenge) -> Rewards:
    return Rewards(first=c.reward_first, second=c.reward_second, third=c.reward_third, complete=c.reward_complete)


async def ranking(db: AsyncSession, challenge_id: str) -> list[tuple[str, int]]:
    """[(회원 번호, 인증 일수)] 순위 순서. 인증을 한 번이라도 한 사람만 들어간다."""
    rows = (await db.execute(
        select(CommonChallengeCert.user_id, func.count(CommonChallengeCert.cert_id), func.max(CommonChallengeCert.created_at))
        .where(CommonChallengeCert.challenge_id == challenge_id).group_by(CommonChallengeCert.user_id))).all()
    rows.sort(key=lambda r: (-r[1], r[2], r[0]))
    return [(uid, int(days)) for uid, days, _ in rows]


async def _participants(db: AsyncSession, challenge_id: str) -> int:
    return int((await db.execute(select(func.count()).select_from(CommonChallengeParticipant)
                                 .where(CommonChallengeParticipant.challenge_id == challenge_id))).scalar_one())


async def _joined(db: AsyncSession, challenge_id: str, user_id: str) -> bool:
    return (await db.execute(select(CommonChallengeParticipant.participant_id).where(
        CommonChallengeParticipant.challenge_id == challenge_id,
        CommonChallengeParticipant.user_id == user_id))).first() is not None


async def _get(db: AsyncSession, challenge_id: str) -> CommonChallenge:
    c = await db.get(CommonChallenge, challenge_id)
    if c is None:
        raise _not_found()
    return c


def _rank_of(rank: list[tuple[str, int]], user_id: str) -> int | None:
    for i, (uid, _) in enumerate(rank, start=1):
        if uid == user_id:
            return i
    return None


# ---------------------------------------------------------------- 이용자
async def _item(db: AsyncSession, c: CommonChallenge, user_id: str, today: date) -> CommonChallengeItem:
    rank = await ranking(db, c.challenge_id)
    return CommonChallengeItem(
        challenge_id=c.challenge_id, title=c.title, proof_type=c.proof_type, starts_on=c.starts_on, ends_on=c.ends_on,
        state=state_of(c, today), participants=await _participants(db, c.challenge_id), max_reward=c.reward_first,
        joined=await _joined(db, c.challenge_id, user_id), my_rank=_rank_of(rank, user_id))


async def list_challenges(db: AsyncSession, user_id: str, state: str | None) -> CommonChallengeList:
    today = today_kst()
    rows = (await db.execute(select(CommonChallenge).order_by(CommonChallenge.starts_on.desc()))).scalars().all()
    items = [await _item(db, c, user_id, today) for c in rows if state is None or state_of(c, today) == state]
    return CommonChallengeList(items=items)


async def detail(db: AsyncSession, user_id: str, challenge_id: str) -> CommonChallengeDetail:
    c = await _get(db, challenge_id)
    today = today_kst()
    base = await _item(db, c, user_id, today)
    rank = await ranking(db, challenge_id)
    wanted = rank[:TOP_N]
    if base.my_rank is not None and base.my_rank > TOP_N:
        wanted = wanted + [rank[base.my_rank - 1]]
    names = {uid: n for uid, n in (await db.execute(select(CommunityProfile.user_id, CommunityProfile.nickname).where(
        CommunityProfile.user_id.in_([u for u, _ in wanted])))).all()} if wanted else {}
    top = [RankRow(rank=_rank_of(rank, uid), nickname=names.get(uid, "알 수 없음"), days=d, is_me=uid == user_id)
           for uid, d in wanted]
    my_days = next((d for uid, d in rank if uid == user_id), 0)
    certified_today = (await db.execute(select(CommonChallengeCert.cert_id).where(
        CommonChallengeCert.challenge_id == challenge_id, CommonChallengeCert.user_id == user_id,
        CommonChallengeCert.cert_date == today))).first() is not None
    return CommonChallengeDetail(
        **base.model_dump(), target_steps=c.target_steps, total_days=total_days(c), complete_min_days=c.complete_min_days,
        rewards=_rewards(c), my_days=my_days, certified_today=certified_today, finalized=c.finalized_at is not None, top=top)


async def join(db: AsyncSession, user_id: str, challenge_id: str) -> JoinResult:
    c = await _get(db, challenge_id)
    await community_service.require_nickname(db, user_id)
    if state_of(c, today_kst()) == "ended":
        raise AppError(409, "COMMON_CHALLENGE_ENDED", "이미 끝난 챌린지예요.")
    if await _joined(db, challenge_id, user_id):
        raise AppError(409, "ALREADY_JOINED", "이미 참여하고 있어요.")
    db.add(CommonChallengeParticipant(challenge_id=challenge_id, user_id=user_id, joined_at=utcnow()))
    await db.commit()
    return JoinResult(participants=await _participants(db, challenge_id))


async def certify(db: AsyncSession, user_id: str, challenge_id: str, req: CertifyRequest) -> CertifyResult:
    c = await _get(db, challenge_id)
    today = today_kst()
    st = state_of(c, today)
    if st != "active":
        raise AppError(409, "COMMON_CHALLENGE_NOT_ACTIVE",
                       "아직 시작하지 않은 챌린지예요." if st == "upcoming" else "이미 끝난 챌린지예요.")
    if not await _joined(db, challenge_id, user_id):
        raise AppError(409, "NOT_JOINED", "먼저 챌린지에 참여해 주세요.")
    steps = None
    if c.proof_type == "steps":
        if req.steps is None:
            raise AppError(422, "STEPS_REQUIRED", "걸음 수를 적어 주세요.")
        if req.steps < (c.target_steps or 0):
            raise AppError(422, "STEPS_NOT_ENOUGH", "목표 걸음 수에 아직 못 미쳤어요.")
        steps = req.steps
    done = (await db.execute(select(CommonChallengeCert.cert_id).where(
        CommonChallengeCert.challenge_id == challenge_id, CommonChallengeCert.user_id == user_id,
        CommonChallengeCert.cert_date == today))).first()
    if done is not None:
        raise AppError(409, "ALREADY_CERTIFIED", "오늘은 이미 인증했어요.")
    db.add(CommonChallengeCert(challenge_id=challenge_id, user_id=user_id, cert_date=today, steps=steps,
                               created_at=utcnow()))
    await db.commit()
    rank = await ranking(db, challenge_id)
    return CertifyResult(my_days=next(d for uid, d in rank if uid == user_id), my_rank=_rank_of(rank, user_id))


# ---------------------------------------------------------------- 관리자
async def _admin_item(db: AsyncSession, c: CommonChallenge, today: date) -> AdminChallengeItem:
    return AdminChallengeItem(
        challenge_id=c.challenge_id, title=c.title, proof_type=c.proof_type, target_steps=c.target_steps,
        starts_on=c.starts_on, ends_on=c.ends_on, state=state_of(c, today),
        participants=await _participants(db, c.challenge_id), complete_min_days=c.complete_min_days,
        rewards=_rewards(c), finalized_at=c.finalized_at)


async def admin_list(db: AsyncSession, admin: str) -> AdminChallengeList:
    today = today_kst()
    rows = (await db.execute(select(CommonChallenge).order_by(CommonChallenge.starts_on.desc()))).scalars().all()
    items = [await _admin_item(db, c, today) for c in rows]
    await audit_service.record(db, admin, "common_challenges_view", dedupe_seconds=audit_service.VIEW_DEDUPE_SECONDS)
    await db.commit()
    return AdminChallengeList(items=items)


def _check_min_days(value: int, days: int) -> None:
    if value > days:
        raise AppError(422, "VALIDATION_ERROR", "완주 기준 일수는 전체 기간보다 길 수 없어요.")


async def admin_create(db: AsyncSession, admin: str, req: ChallengeCreate) -> AdminChallengeItem:
    days = (req.ends_on - req.starts_on).days + 1
    min_days = req.complete_min_days or max(1, math.ceil(days * DEFAULT_COMPLETE_RATE))
    _check_min_days(min_days, days)
    c = CommonChallenge(
        title=req.title, proof_type=req.proof_type, target_steps=req.target_steps, starts_on=req.starts_on,
        ends_on=req.ends_on, complete_min_days=min_days, reward_first=req.reward_first, reward_second=req.reward_second,
        reward_third=req.reward_third, reward_complete=req.reward_complete, created_by=admin, created_at=utcnow())
    db.add(c)
    await db.flush()
    await audit_service.record(db, admin, "common_challenge_create", target=c.challenge_id[-8:])
    await db.commit()
    return await _admin_item(db, c, today_kst())


async def admin_patch(db: AsyncSession, admin: str, challenge_id: str, req: ChallengePatch) -> AdminChallengeItem:
    c = await _get(db, challenge_id)
    if c.finalized_at is not None:
        raise AppError(409, "COMMON_CHALLENGE_FINALIZED", "이미 순위를 확정한 챌린지라 고칠 수 없어요.")
    data = req.model_dump(exclude_unset=True)
    if data.get("complete_min_days") is not None:
        _check_min_days(data["complete_min_days"], total_days(c))
    for k, v in data.items():
        if v is not None:
            setattr(c, k, v)
    await audit_service.record(db, admin, "common_challenge_update", target=c.challenge_id[-8:])
    await db.commit()
    return await _admin_item(db, c, today_kst())


async def admin_finalize(db: AsyncSession, admin: str, challenge_id: str) -> FinalizeResult:
    c = await _get(db, challenge_id)
    if c.finalized_at is not None:
        raise AppError(409, "COMMON_CHALLENGE_FINALIZED", "이미 순위를 확정했어요.")
    if state_of(c, today_kst()) != "ended":
        raise AppError(409, "COMMON_CHALLENGE_NOT_ENDED", "챌린지가 끝난 뒤에 확정할 수 있어요.")
    rank = await ranking(db, challenge_id)
    top_rewards = [c.reward_first, c.reward_second, c.reward_third]
    ranked = completed = total = 0
    for i, (uid, days) in enumerate(rank):
        if i < 3:
            if await pie_service.add(db, uid, top_rewards[i], pie_service.RANK, challenge_id):
                ranked += 1
                total += top_rewards[i]
        elif days >= c.complete_min_days:
            if await pie_service.add(db, uid, c.reward_complete, pie_service.COMPLETE, challenge_id):
                completed += 1
                total += c.reward_complete
    c.finalized_at = utcnow()
    await audit_service.record(db, admin, "common_challenge_finalize", target=c.challenge_id[-8:])
    await db.commit()
    return FinalizeResult(challenge_id=challenge_id, ranked=ranked, completed=completed, total_pie=total)
