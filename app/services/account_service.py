"""회원 탈퇴 매니저. 재인증(비밀번호) → 내 데이터 전부 삭제 → 계정 익명화.
ERD 규칙: users 행은 지우지 않고 email을 'deleted+{id}@invalid'로 바꾸고 status='deleted', deleted_at을 남긴다."""
from datetime import datetime
from app.models.user import UserProfile

from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import Base
from app.core.errors import AppError
from app.core.security import hash_password_async, new_refresh_token, utcnow, verify_password_async
from app.models.deletion import AccountDeletionRequest
from app.models.health import HealthMeasurement, HealthRecord
from app.repositories import user_repository

KEEP_TABLES = {"users", "account_deletion_requests"}  # 이 둘은 지우지 않는다 (익명화 / 탈퇴 기록)


class DeletionResult(BaseModel):
    deletion_request_id: str
    status: str
    requested_at: datetime
    completed_at: datetime | None
    result_summary: dict | None


def _result(r: AccountDeletionRequest) -> DeletionResult:
    return DeletionResult(deletion_request_id=r.deletion_request_id, status=r.status, requested_at=r.requested_at,
                          completed_at=r.completed_at, result_summary=r.result_summary)


# 건강정보 동의 철회 때 남기는 표: 계정·프로필·로그인 세션·동의 기록, 문의, 커뮤니티 닉네임·글·댓글(건강정보가 아니라서)
# (+ 탈퇴 때도 남기는 표). 파이 장부와 공통 챌린지 참여·인증 기록은 건강 활동에서 나온 것이라 철회 때 지운다.
# 배지·파티·캐릭터 표를 만들 때는 이 목록을 보고 남길지 지울지 정한다 (캐릭터만 남기고 파이·배지·파티는 지운다).
HEALTH_KEEP_TABLES = KEEP_TABLES | {
    "users", "user_profiles", "user_sessions", "user_consents", "inquiries",
    "community_profiles", "community_posts", "community_comments", "community_likes", "community_reports",
    "character_items", "user_characters",
}


async def _delete_user_rows(db: AsyncSession, user_id: str, keep: set[str]) -> dict[str, int]:
    """user_id 칸이 있는 표를 자식부터 지운다 (keep에 있는 표는 남김). 탈퇴·동의 철회가 같이 쓴다."""
    # 이월(carried_forward) 측정값이 서로를 가리키므로, 지우기 전에 연결을 끊어 둔다
    await db.execute(update(HealthMeasurement).where(HealthMeasurement.health_record_id.in_(
        select(HealthRecord.health_record_id).where(HealthRecord.user_id == user_id))).values(source_measurement_id=None))
    # user_id가 없는 자식(측정값·답·요인·로그)은 FK CASCADE로 같이 지워진다.
    summary: dict[str, int] = {}
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in keep or "user_id" not in table.c:
            continue
        count = (await db.execute(delete(table).where(table.c.user_id == user_id))).rowcount
        if count:
            summary[table.name] = count
    return summary


async def delete_account_data(db: AsyncSession, user) -> AccountDeletionRequest:
    """탈퇴: 데이터 정리 + 계정 익명화. commit은 부르는 쪽에서."""
    now = utcnow()
    req = AccountDeletionRequest(user_id=user.user_id, reauthenticated_at=now, requested_at=now, status="processing")
    db.add(req)
    await db.flush()
    summary = await _delete_user_rows(db, user.user_id, KEEP_TABLES)
    user.email = f"deleted+{user.user_id}@invalid"
    user.password_hash = await hash_password_async(new_refresh_token())   # 아무도 모르는 값으로 바꿔 로그인 불가
    user.status = "deleted"
    user.deleted_at = now
    req.status, req.completed_at, req.result_summary = "completed", utcnow(), summary
    return req


async def delete_health_data(db: AsyncSession, user_id: str) -> dict[str, int]:
    """건강정보 동의 철회: 계정·생년월일·세션·동의 기록은 남기고 건강 관련 데이터와 성별을 지운다.
    commit은 부르는 쪽에서."""
    summary = await _delete_user_rows(db, user_id, HEALTH_KEEP_TABLES)
    profile = await db.get(UserProfile, user_id)
    if profile is not None and profile.sex is not None:
        profile.sex = None   # 성별은 건강정보 입력 화면에서 받는 값이라 같이 비운다 (생년월일은 계정 정보라 유지)
        summary["user_profiles.sex"] = 1
    return summary


async def request_deletion(db: AsyncSession, user_id: str, password: str) -> DeletionResult:
    user = await user_repository.get_user_by_id(db, user_id)
    if user is None or user.status == "deleted":
        raise AppError(401, "AUTH_UNAUTHORIZED", "다시 로그인해 주세요.")
    if not await verify_password_async(password, user.password_hash):
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "비밀번호가 맞지 않습니다.")
    req = await delete_account_data(db, user)
    await db.commit()
    return _result(req)


async def get_deletion(db: AsyncSession, user_id: str, deletion_request_id: str) -> DeletionResult:
    req = await db.get(AccountDeletionRequest, deletion_request_id)
    if req is None or req.user_id != user_id:
        raise AppError(404, "DELETION_REQUEST_NOT_FOUND", "탈퇴 요청을 찾을 수 없습니다.")
    return _result(req)


# 내려받기에서 뺄 칸 (비밀번호·로그인 토큰 해시, 암호화된 보호자 정보)
EXPORT_SKIP_COLUMNS = {"password_hash", "refresh_token_hash", "guardian_name_enc", "guardian_contact_enc"}
# user_id 칸이 없는 자식 표 → (부모 표, 연결 칸): 부모가 내 것이면 같이 담는다
EXPORT_CHILDREN = {
    "health_measurements": ("health_records", "health_record_id"),
    "survey_responses": ("survey_instances", "survey_instance_id"),
    "prediction_factors": ("predictions", "prediction_id"),
    "cycle_challenges": ("challenge_cycles", "cycle_id"),
    "challenge_logs": ("cycle_challenges", "cycle_challenge_id"),
}


async def export_my_data(db: AsyncSession, user_id: str) -> dict:
    """내 데이터를 표 이름별 목록으로 모은다 (탈퇴 전 내려받기). 탈퇴한 계정은 401."""
    user = await user_repository.get_user_by_id(db, user_id)
    if user is None or user.status == "deleted":
        raise AppError(401, "AUTH_UNAUTHORIZED", "다시 로그인해 주세요.")
    tables = {t.name: t for t in Base.metadata.sorted_tables}

    async def rows(table, where):
        cols = [c for c in table.c if c.name not in EXPORT_SKIP_COLUMNS]
        result = await db.execute(select(*cols).where(where))
        return [dict(r._mapping) for r in result]

    data: dict[str, list[dict]] = {"users": await rows(tables["users"], tables["users"].c.user_id == user_id)}
    for name, table in tables.items():
        if name in ("users", "account_deletion_requests"):
            continue
        if "user_id" in table.c:
            data[name] = await rows(table, table.c.user_id == user_id)
        elif name in EXPORT_CHILDREN:
            parent, key = EXPORT_CHILDREN[name]
            ids = [r[key] for r in data.get(parent, [])]
            data[name] = await rows(table, table.c[key].in_(ids)) if ids else []
    return jsonable_encoder({"exported_at": utcnow(), "data": {k: v for k, v in data.items() if v}})
