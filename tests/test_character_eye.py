"""캐릭터 눈 색: 기본 5개 무료, 3개는 10파이(사야 쓸 수 있음). 눈 색 없이 저장하는 옛 화면은 기본 검정."""
import pytest

from app.services import pie_service
from tests.test_community import make

pytestmark = pytest.mark.asyncio

BASE = {"body": "mongle", "color": "#AACDDC", "expr": "basic", "face": "none", "head": "none"}


async def test_눈_색_무료는_바로_유료는_사야_쓴다(client, db_session):
    uid, h = await make(db_session, "eye@test.kr")
    items = (await client.get("/v1/characters/items", headers=h)).json()["data"]["slots"]
    eye = next(s for s in items if s["slot"] == "eye")["items"]
    assert [i["price"] for i in eye] == [0, 0, 0, 0, 0, 10, 10, 10] and eye[0]["key"] == "#243749"
    assert (await client.get("/v1/characters/me", headers=h)).json()["data"]["eye"] == "#243749"       # 저장 안 했으면 기본 검정
    assert (await client.put("/v1/characters/me", json={**BASE, "eye": "#6FA3D8"}, headers=h)).json()["data"]["eye"] == "#6FA3D8"   # 무료
    assert (await client.put("/v1/characters/me", json={**BASE, "eye": "#E57373"}, headers=h)).status_code == 409                    # 유료인데 안 샀음
    async with db_session() as s:
        assert await pie_service.add(s, uid, 10, "welcome", "t")
        await s.commit()
    assert (await client.post("/v1/characters/items/buy", json={"item_key": "eye:#E57373"}, headers=h)).status_code == 200
    assert (await client.put("/v1/characters/me", json={**BASE, "eye": "#E57373"}, headers=h)).json()["data"]["eye"] == "#E57373"
    assert (await client.put("/v1/characters/me", json={**BASE, "eye": "#123456"}, headers=h)).status_code == 422                    # 없는 색
    assert (await client.put("/v1/characters/me", json=BASE, headers=h)).json()["data"]["eye"] == "#243749"                         # 옛 화면: 눈 색 없이 저장 → 기본
