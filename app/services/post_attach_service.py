"""글에 붙이는 챌린지 카드. "오늘 인증한" 내 4주 챌린지 미션이나 공통 챌린지만 붙일 수 있고,
서버가 직접 확인해서 미션 이름과 인증 일수만 글에 저장한다 (화면이 보낸 값을 믿지 않고, 혈압·걸음 수 같은 수치는 담지 않는다).
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.challenge import Challenge, ChallengeCycle, ChallengeLog, CycleChallenge
from app.models.common_challenge import CommonChallenge, CommonChallengeCert, CommonChallengeParticipant
from app.schemas.community import AttachOption, AttachRequest
from app.services.challenge_service import today_kst


def _kind(selection_type: str) -> str:
    return "selected" if selection_type == "selected" else "fixed"       # 흡연·음주 칸과 그 대체 미션은 고정


async def options(db: AsyncSession, user_id: str) -> list[AttachOption]:
    """오늘 인증한 미션과 공통 챌린지 (글쓰기 화면에서 고르는 후보)."""
    today = today_kst()
    out: list[AttachOption] = []
    cycle = (await db.execute(select(ChallengeCycle).where(
        ChallengeCycle.user_id == user_id, ChallengeCycle.status == "active")
        .order_by(ChallengeCycle.started_on.desc()))).scalars().first()
    if cycle is not None:
        rows = (await db.execute(
            select(CycleChallenge, Challenge).join(Challenge, Challenge.challenge_id == CycleChallenge.challenge_id)
            .where(CycleChallenge.cycle_id == cycle.cycle_id))).all()
        for cc, ch in rows:
            done_today = (await db.execute(select(ChallengeLog.challenge_log_id).where(
                ChallengeLog.cycle_challenge_id == cc.cycle_challenge_id, ChallengeLog.log_date == today,
                ChallengeLog.status == "completed"))).first() is not None
            if done_today:
                out.append(AttachOption(mission_code=ch.challenge_code, common_challenge_id=None,
                                        kind=_kind(cc.selection_type), label=ch.challenge_name,
                                        days=await _mission_days(db, cc.cycle_challenge_id)))
    certs = (await db.execute(
        select(CommonChallenge).join(CommonChallengeCert, CommonChallengeCert.challenge_id == CommonChallenge.challenge_id)
        .where(CommonChallengeCert.user_id == user_id, CommonChallengeCert.cert_date == today))).scalars().all()
    for c in certs:
        out.append(AttachOption(mission_code=None, common_challenge_id=c.challenge_id, kind="common", label=c.title,
                                days=await _common_days(db, c.challenge_id, user_id)))
    return out


async def _mission_days(db: AsyncSession, cycle_challenge_id: str) -> int:
    return int((await db.execute(select(func.count()).select_from(ChallengeLog).where(
        ChallengeLog.cycle_challenge_id == cycle_challenge_id, ChallengeLog.status == "completed"))).scalar_one())


async def _common_days(db: AsyncSession, challenge_id: str, user_id: str) -> int:
    return int((await db.execute(select(func.count()).select_from(CommonChallengeCert).where(
        CommonChallengeCert.challenge_id == challenge_id, CommonChallengeCert.user_id == user_id))).scalar_one())


def _not_allowed() -> AppError:
    return AppError(409, "ATTACH_NOT_ALLOWED", "오늘 인증한 챌린지만 붙일 수 있어요.")


async def resolve(db: AsyncSession, user_id: str, req: AttachRequest) -> tuple[str, str, int]:
    """붙일 챌린지를 확인하고 (종류, 이름, 인증 일수)를 돌려준다. 오늘 인증하지 않았거나 내 것이 아니면 거절한다."""
    if req.party_card:                      # 파티 카드는 파티 글을 쓸 때만 (파티 글쓰기가 따로 처리한다)
        raise _not_allowed()
    for o in await options(db, user_id):
        if req.mission_code and o.mission_code == req.mission_code:
            return o.kind, o.label, o.days
        if req.common_challenge_id and o.common_challenge_id == req.common_challenge_id:
            return o.kind, o.label, o.days
    raise _not_allowed()
