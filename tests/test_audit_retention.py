"""관리자 기록 보관 기간: 행위 기록은 2년, 권한 부여·회수 기록은 3년(안전성 확보조치 기준)."""
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.security import utcnow
from app.models.admin_audit import AdminAuditLog
from app.services import audit_service

pytestmark = pytest.mark.asyncio
DAY = timedelta(days=1)


async def add(s, action: str, age: timedelta, target: str) -> None:
    s.add(AdminAuditLog(actor_email="a@test.kr", action=action, target=target, created_at=utcnow() - age))


async def test_행위_기록은_2년_권한_기록은_3년_남는다(db_session):
    two, three = timedelta(days=audit_service.RETENTION_DAYS), timedelta(days=audit_service.GRANT_RETENTION_DAYS)
    async with db_session() as s:
        await add(s, "user_list_view", two + DAY, "view-old")        # 2년 넘은 행위 기록 → 지움
        await add(s, "user_list_view", two - DAY, "view-recent")     # 2년 안 → 남김
        await add(s, "admin_granted", two + DAY, "grant-2y")         # 2년 넘었지만 권한 기록 → 남김
        await add(s, "admin_revoked", three - DAY, "revoke-3y-in")   # 3년 안 → 남김
        await add(s, "admin_granted", three + DAY, "grant-old")      # 3년 넘은 권한 기록 → 지움
        await s.commit()
        await audit_service.record(s, "a@test.kr", "user_detail_view", target="now")   # 새 기록을 남길 때 정리됨
        await s.commit()
        left = set((await s.execute(select(AdminAuditLog.target))).scalars())
    assert left == {"view-recent", "grant-2y", "revoke-3y-in", "now"}


async def test_권한_기록_보관이_행위_기록보다_길다():
    assert audit_service.GRANT_RETENTION_DAYS >= 3 * 365 > audit_service.RETENTION_DAYS
    assert set(audit_service.GRANT_ACTIONS) == {"admin_granted", "admin_revoked"}
