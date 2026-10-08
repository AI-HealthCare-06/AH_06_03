"""회원 탈퇴 매니저. 재인증(비밀번호) → 내 데이터 전부 삭제 → 계정 익명화.
ERD 규칙: users 행은 지우지 않고 email을 'deleted+{id}@invalid'로 바꾸고 status='deleted', deleted_at을 남긴다."""
from datetime import datetime

from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import Base
from app.core.errors import AppError
from app.core.security import hash_password, new_refresh_token, utcnow, verify_password
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


async def request_deletion(db: AsyncSession, user_id: str, password: str) -> DeletionResult:
    user = await user_repository.get_user_by_id(db, user_id)
    if user is None or user.status == "deleted":
        raise AppError(401, "AUTH_UNAUTHORIZED", "다시 로그인해 주세요.")
    if not verify_password(password, user.password_hash):
        raise AppError(401, "AUTH_INVALID_CREDENTIALS", "비밀번호가 맞지 않습니다.")
    now = utcnow()
    req = AccountDeletionRequest(user_id=user_id, reauthenticated_at=now, requested_at=now, status="processing")
    db.add(req)
    await db.flush()
    # 이월(carried_forward) 측정값이 서로를 가리키므로, 지우기 전에 연결을 끊어 둔다
    await db.execute(update(HealthMeasurement).where(HealthMeasurement.health_record_id.in_(
        select(HealthRecord.health_record_id).where(HealthRecord.user_id == user_id))).values(source_measurement_id=None))
    # user_id 칸이 있는 표를 자식부터 지운다. user_id가 없는 자식(측정값·답·요인)은 FK CASCADE로 같이 지워진다.
    summary: dict[str, int] = {}
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in KEEP_TABLES or "user_id" not in table.c:
            continue
        count = (await db.execute(delete(table).where(table.c.user_id == user_id))).rowcount
        if count:
            summary[table.name] = count
    user.email = f"deleted+{user_id}@invalid"
    user.password_hash = hash_password(new_refresh_token())   # 아무도 모르는 값으로 바꿔 로그인 불가
    user.status = "deleted"
    user.deleted_at = now
    req.status, req.completed_at, req.result_summary = "completed", utcnow(), summary
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
