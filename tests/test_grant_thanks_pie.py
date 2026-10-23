"""감사 파이 지급: 기간(한국 날짜) 안 가입자만, 두 번 돌려도 한 번만, 미리보기는 지급 안 함."""
from datetime import date, datetime

import pytest
from sqlalchemy import update

from app.models.user import User
from app.scripts import grant_thanks_pie as g
from app.services import pie_service
from tests.test_community import make

pytestmark = pytest.mark.asyncio


def test_kst_range():
    lo, hi = g.kst_range_to_utc(date(2026, 10, 22), date(2026, 10, 23))
    assert lo == datetime(2026, 10, 21, 15, 0) and hi == datetime(2026, 10, 23, 15, 0)


async def test_기간_안_가입자에게만_한_번_지급(db_session):
    inside, _ = await make(db_session, "in@test.kr")
    edge, _ = await make(db_session, "edge@test.kr")
    outside, _ = await make(db_session, "out@test.kr")
    # 한국 10/23 23:59 가입(=UTC 14:59) 은 포함, 한국 10/24 00:00(=UTC 15:00) 은 제외
    async with db_session() as db:
        for uid, at in ((inside, datetime(2026, 10, 22, 3, 0)), (edge, datetime(2026, 10, 23, 14, 59)), (outside, datetime(2026, 10, 23, 15, 0))):
            await db.execute(update(User).where(User.user_id == uid).values(created_at=at))
        await db.commit()
        args = (date(2026, 10, 22), date(2026, 10, 23), 200, "2026-10")
        assert await g.grant(db, *args, apply=False) == (2, 0)                      # 미리보기는 지급하지 않는다
        assert await pie_service.balance(db, inside) == 0
        assert await g.grant(db, *args, apply=True) == (2, 2)
        assert await g.grant(db, *args, apply=True) == (2, 0)                       # 다시 돌려도 중복 지급 없음
        assert [await pie_service.balance(db, u) for u in (inside, edge, outside)] == [200, 200, 0]
