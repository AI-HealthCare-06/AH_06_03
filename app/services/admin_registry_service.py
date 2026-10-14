"""관리자 권한 부여·회수 기록. 관리자는 서버 설정(ADMIN_EMAILS)으로 정해지므로, 서버가 켜질 때 목록을 지난 기록과 비교해
새로 들어온 이메일은 '권한 부여', 빠진 이메일은 '권한 회수'로 관리자 행위 기록에 남긴다 (설정을 바꾼 사람은 알 수 없고, 반영된 시점만 남는다)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import utcnow
from app.models.admin_audit import AdminAuditLog

SYSTEM_ACTOR = "system(서버 설정)"
GRANT, REVOKE = "admin_granted", "admin_revoked"


async def sync_admin_log(db: AsyncSession) -> tuple[list[str], list[str]]:
    """(새로 부여한 이메일, 회수한 이메일)을 돌려준다. 같은 상태로 다시 켜져도 기록을 또 남기지 않는다."""
    rows = (await db.execute(
        select(AdminAuditLog.target, AdminAuditLog.action)
        .where(AdminAuditLog.action.in_((GRANT, REVOKE)))
        .order_by(AdminAuditLog.created_at, AdminAuditLog.audit_id)
    )).all()
    granted = {t for t, a in rows if a == GRANT}
    for t, a in rows:                      # 같은 이메일의 가장 최근 동작만 본다
        if a == REVOKE:
            granted.discard(t)
        else:
            granted.add(t)
    current = {e[:100] for e in settings.admin_email_set}
    now = utcnow()
    added, removed = sorted(current - granted), sorted(granted - current)
    for e in added:
        db.add(AdminAuditLog(actor_email=SYSTEM_ACTOR, action=GRANT, target=e, detail="서버 설정의 관리자 목록에 추가됨", created_at=now))
    for e in removed:
        db.add(AdminAuditLog(actor_email=SYSTEM_ACTOR, action=REVOKE, target=e, detail="서버 설정의 관리자 목록에서 빠짐", created_at=now))
    await db.commit()
    return added, removed
