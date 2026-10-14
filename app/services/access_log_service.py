"""서비스 접속(로그인) 기록. 3개월(93일)이 지난 기록은 새 기록을 남길 때 함께 지운다."""
from datetime import timedelta

from fastapi import Request
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models.access_log import AccessLog

RETENTION_DAYS = 93   # 3개월(최대 92일) 이상 보관해야 하므로 여유를 둔다


def client_ip(request: Request) -> str | None:
    """Caddy 뒤에서 도는 서버라 실제 방문자 IP는 X-Forwarded-For의 첫 값이다 (Caddy가 바깥에서 온 값은 덮어쓴다)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:45] or None
    return request.client.host[:45] if request.client else None


async def record_login(db: AsyncSession, account_id: str, ip: str | None) -> None:
    """로그인 기록을 더하고 보관 기간이 지난 기록을 지운다 (commit은 부르는 쪽에서)."""
    now = utcnow()
    await db.execute(delete(AccessLog).where(AccessLog.created_at < now - timedelta(days=RETENTION_DAYS)))
    db.add(AccessLog(account_id=account_id, event="login", ip=ip, created_at=now))
