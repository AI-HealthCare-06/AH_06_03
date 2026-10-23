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


async def test_공지_카드로_받기_기간_안만_한_번만(client, db_session, monkeypatch):
    inside, h_in = await make(db_session, "in2@test.kr")
    outside, h_out = await make(db_session, "out2@test.kr")
    async with db_session() as db:
        await db.execute(update(User).where(User.user_id == inside).values(created_at=datetime(2026, 10, 22, 3, 0)))
        await db.execute(update(User).where(User.user_id == outside).values(created_at=datetime(2026, 10, 24, 0, 0)))   # 한국 10/24 09:00 = 기간 밖
        await db.commit()
    monkeypatch.setattr(pie_service, "THANKS_UNTIL", date(2999, 1, 1))                                         # 받는 기한은 시험 날짜와 무관하게
    assert (await client.get("/v1/pie/thanks", headers=h_in)).json()["data"] == {"eligible": True, "claimed": False, "amount": 200}
    assert (await client.post("/v1/pie/thanks", headers=h_out)).status_code == 403     # 기간 밖 가입자
    r = await client.post("/v1/pie/thanks", headers=h_in)
    assert r.status_code == 200 and r.json()["data"]["claimed"] is True
    await client.post("/v1/pie/thanks", headers=h_in)                                   # 다시 눌러도 한 번만
    assert (await client.get("/v1/pie", headers=h_in)).json()["data"]["balance"] == 200
