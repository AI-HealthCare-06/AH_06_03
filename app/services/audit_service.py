"""관리자 행위 기록 (REQ-ADM-005). 열람은 같은 관리자가 같은 화면을 새로고침할 때마다 쌓이지 않게 한동안 한 번만 남긴다."""
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models.admin_audit import AdminAuditLog
from app.schemas.admin import AuditLogItem
from app.services.admin_registry_service import GRANT, REVOKE

VIEW_DEDUPE_SECONDS = 600
RETENTION_DAYS = 730          # 관리자 행위 기록은 2년 보관하고, 새 기록을 남길 때 그보다 오래된 기록을 지운다
# 관리자 권한 부여·회수 기록은 3년: 개인정보의 안전성 확보조치 기준이 개인정보취급자의 접근 권한
# 부여·변경·말소 내역을 최소 3년 보관하라고 함 (2026-10-20 멘토링·팀 점검에서 확인)
GRANT_RETENTION_DAYS = 1095
GRANT_ACTIONS = (GRANT, REVOKE)


async def record(
    db: AsyncSession, actor_email: str, action: str, target: str | None = None, detail: str | None = None,
    dedupe_seconds: int = 0,
) -> bool:
    """기록을 더한다 (commit은 부르는 쪽에서). 막 같은 기록을 남겼다면 건너뛰고 False를 돌려준다."""
    now = utcnow()
    await db.execute(delete(AdminAuditLog).where(
        AdminAuditLog.created_at < now - timedelta(days=RETENTION_DAYS), AdminAuditLog.action.not_in(GRANT_ACTIONS)))
    await db.execute(delete(AdminAuditLog).where(
        AdminAuditLog.created_at < now - timedelta(days=GRANT_RETENTION_DAYS), AdminAuditLog.action.in_(GRANT_ACTIONS)))
    if dedupe_seconds:
        last = (await db.execute(
            select(func.max(AdminAuditLog.created_at))
            .where(AdminAuditLog.actor_email == actor_email, AdminAuditLog.action == action)
        )).scalar_one()
        if last is not None and (now - last).total_seconds() < dedupe_seconds:
            return False
    db.add(AdminAuditLog(actor_email=actor_email, action=action, target=target,
                         detail=detail[:500] if detail else None, created_at=now))
    await db.flush()
    return True


async def list_logs(db: AsyncSession, limit: int) -> list[AuditLogItem]:
    rows = (await db.execute(
        select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.audit_id).limit(limit)
    )).scalars().all()
    return [AuditLogItem(created_at=r.created_at, actor_email=r.actor_email, action=r.action, target=r.target, detail=r.detail)
            for r in rows]
