"""동의 매니저: 현재 유효한 정책 조회, 동의·철회 기록, 건강정보 동의 철회 여부 확인."""
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.consent import ConsentPolicy, UserConsent

from app.services import account_service

SIGNUP_POLICY_TYPES = ("terms_of_service", "privacy", "health_data")  # 가입 화면의 필수 동의 체크박스


class PolicyResult(BaseModel):
    policy_id: str
    policy_type: str
    version: str
    purpose_text: str
    collection_items: str
    retention_policy: str
    withdrawal_method: str
    third_party_notice: str
    published_at: datetime


class ConsentResult(BaseModel):
    policy_id: str
    policy_type: str
    version: str
    status: str
    consented_at: datetime
    withdrawn_at: datetime | None
    deleted_counts: dict[str, int] = Field(default_factory=dict)   # 표별 삭제 건수 (건강정보 철회 때만)
    deleted_total: int = 0


async def _active_policies(db: AsyncSession) -> list[ConsentPolicy]:
    """종류별로 가장 최근에 공개된 정책 (보호자 동의 정책은 제외)."""
    rows = (await db.execute(select(ConsentPolicy).where(ConsentPolicy.policy_type != "guardian")
                             .order_by(ConsentPolicy.published_at.desc(), ConsentPolicy.version.desc()))).scalars().all()
    latest: dict[str, ConsentPolicy] = {}
    for p in rows:
        latest.setdefault(p.policy_type, p)
    return list(latest.values())


async def list_active_policies(db: AsyncSession) -> list[PolicyResult]:
    return [PolicyResult.model_validate(p, from_attributes=True) for p in await _active_policies(db)]


async def check_signup_consents(db: AsyncSession, consents: list) -> list[ConsentPolicy]:
    """가입 화면이 보낸 동의가 지금 유효한 필수 정책 전부에 대한 '동의'인지 확인한다. 맞으면 그 정책들을 돌려준다.
    - 정책 ID·버전이 지금 유효한 것과 다르면 409 (약관이 바뀐 뒤에 낡은 화면에서 가입한 경우)
    - 필수 정책이 빠졌거나 동의하지 않았으면 422"""
    active = {p.policy_type: p for p in await _active_policies(db) if p.policy_type in SIGNUP_POLICY_TYPES}
    by_id = {p.policy_id: p for p in active.values()}
    sent: dict[str, bool] = {}
    for c in consents:
        p = by_id.get(c.policy_id)
        if p is None or p.version != c.version:
            raise AppError(409, "CONSENT_POLICY_OUTDATED", "약관이 새로 바뀌었어요. 화면을 새로고침한 뒤 다시 동의해 주세요.")
        if c.policy_id in sent:
            raise AppError(422, "CONSENT_DUPLICATED", "같은 약관에 대한 동의가 두 번 들어왔어요.")
        sent[c.policy_id] = c.agreed
    for p in active.values():
        if sent.get(p.policy_id) is not True:
            raise AppError(422, "CONSENT_REQUIRED", "필수 동의 항목에 모두 동의해야 가입할 수 있어요.")
    return list(active.values())


async def record_signup_consents(db: AsyncSession, user_id: str, policies: list[ConsentPolicy]) -> None:
    """사용자가 동의한 정책(check_signup_consents를 통과한 것)의 동의 기록을 남긴다 (commit은 부른 쪽이)."""
    now = utcnow()
    for p in policies:
        db.add(UserConsent(user_id=user_id, policy_id=p.policy_id, status="agreed", consented_at=now))


async def list_my_consents(db: AsyncSession, user_id: str) -> list[ConsentResult]:
    """정책마다 가장 최근 동의·철회 기록."""
    rows = (await db.execute(
        select(UserConsent, ConsentPolicy).join(ConsentPolicy, ConsentPolicy.policy_id == UserConsent.policy_id)
        .where(UserConsent.user_id == user_id)
        .order_by(UserConsent.consented_at.desc(), UserConsent.user_consent_id.desc())
    )).all()
    latest: dict[str, ConsentResult] = {}
    for c, p in rows:
        latest.setdefault(c.policy_id, ConsentResult(
            policy_id=c.policy_id, policy_type=p.policy_type, version=p.version,
            status=c.status, consented_at=c.consented_at, withdrawn_at=c.withdrawn_at))
    return list(latest.values())


async def _get_policy(db: AsyncSession, policy_id: str) -> ConsentPolicy:
    p = await db.get(ConsentPolicy, policy_id)
    if p is None:
        raise AppError(404, "CONSENT_POLICY_NOT_FOUND", "동의 정책을 찾을 수 없습니다.")
    return p


async def _current(db: AsyncSession, user_id: str, policy_id: str) -> UserConsent | None:
    return (await db.execute(
        select(UserConsent).where(UserConsent.user_id == user_id, UserConsent.policy_id == policy_id)
        .order_by(UserConsent.consented_at.desc(), UserConsent.user_consent_id.desc()).limit(1)
    )).scalar_one_or_none()


def _result(policy, c, deleted: dict[str, int] | None = None) -> ConsentResult:
    deleted = deleted or {}
    return ConsentResult(policy_id=policy.policy_id, policy_type=policy.policy_type, version=policy.version,
                         status=c.status, consented_at=c.consented_at, withdrawn_at=c.withdrawn_at,
                         deleted_counts=deleted,
                        deleted_total=sum(deleted.values()),)


async def agree(db: AsyncSession, user_id: str, policy_id: str) -> ConsentResult:
    """동의(철회 뒤 다시 동의 포함). 이미 동의 중이면 그대로 돌려준다."""
    policy = await _get_policy(db, policy_id)
    cur = await _current(db, user_id, policy_id)
    if cur is None or cur.status == "withdrawn":
        cur = UserConsent(user_id=user_id, policy_id=policy_id, status="agreed", consented_at=utcnow())
        db.add(cur)
        await db.commit()
    return _result(policy, cur)


async def withdraw(db: AsyncSession, user_id: str, policy_id: str) -> ConsentResult:
    """동의 철회 (회원 탈퇴가 아님: 계정은 유지). 동의한 적이 없으면 404.
    건강정보 동의를 철회하면 건강 관련 데이터를 같은 트랜잭션에서 바로 삭제한다 (탈퇴와 같은 삭제 함수 사용)."""
    policy = await _get_policy(db, policy_id)
    cur = await _current(db, user_id, policy_id)
    if cur is None:
        raise AppError(404, "CONSENT_NOT_FOUND", "동의 기록이 없습니다.")
    deleted: dict[str, int] = {}
    if cur.status == "agreed":
        cur.status, cur.withdrawn_at = "withdrawn", utcnow()
        if policy.policy_type == "health_data":
            deleted = await account_service.delete_health_data(db, user_id)
            cur.deletion_summary = deleted
        await db.commit()   # 철회 + 삭제를 한 번에. 삭제 중 오류가 나면 철회도 같이 취소된다
    return _result(policy, cur, deleted)


async def health_consent_withdrawn(db: AsyncSession, user_id: str) -> bool:
    """건강정보 동의를 철회한 상태인가? 기록이 없는 기존 회원은 철회가 아닌 것으로 본다."""
    for c in await list_my_consents(db, user_id):
        if c.policy_type == "health_data":
            return c.status == "withdrawn"
    return False
