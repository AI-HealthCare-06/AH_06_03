"""파티 피드: 파티 글은 그 파티원에게만 보이고, 전체 커뮤니티에는 나오지 않으며, 파티가 없어지면 글도 사라진다."""
import pytest
from sqlalchemy import select

from app.apis.consent import require_health_consent
from app.main import app
from app.models.community import CommunityPost
from app.models.pie import PieLedger
from app.services import party_service as ps
from tests.test_community import with_nick

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def consent_ok():
    app.dependency_overrides[require_health_consent] = lambda: None   # 이 시험은 동의 확인이 아니라 글 범위를 본다
    yield
    app.dependency_overrides.pop(require_health_consent, None)


async def _setup(client, Session):
    a, ha = await with_nick(client, Session, "a@t.kr", "가가")
    b, hb = await with_nick(client, Session, "b@t.kr", "나나")
    c, hc = await with_nick(client, Session, "c@t.kr", "다다")
    async with Session() as s:
        code = (await ps.challenge_options(s))[0].challenge_code
        info = await ps.create(s, a, "아침걷기", None, code)
    async with Session() as s:
        await ps.join(s, b, info.invite_code)
    return (a, ha), (b, hb), (c, hc)


POST = {"category": "tips", "title": "파티 글", "body": "파티원끼리 나누는 글"}


async def test_파티원은_파티_글을_쓰고_본다_밖의_사람은_못_본다(client, db_session):
    (a, ha), (b, hb), (c, hc) = await _setup(client, db_session)
    r = await client.post("/v1/parties/me/posts", json=POST, headers=ha)
    assert r.status_code == 201 and r.json()["data"]["pie_gain"] == 0          # 파티 글은 파이를 주지 않는다
    pid = r.json()["data"]["post_id"]

    mine = await client.get("/v1/parties/me/posts", headers=hb)                # 같은 파티원
    assert [i["post_id"] for i in mine.json()["data"]["items"]] == [pid]
    assert (await client.get(f"/v1/community/posts/{pid}", headers=hb)).status_code == 200

    assert (await client.get("/v1/parties/me/posts", headers=hc)).status_code == 404   # 파티 없는 사람
    assert (await client.get(f"/v1/community/posts/{pid}", headers=hc)).status_code == 404
    assert (await client.post(f"/v1/community/posts/{pid}/like", headers=hc)).status_code == 404
    assert (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "끼어들기"}, headers=hc)).status_code == 404
    assert (await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "spam"}, headers=hc)).status_code == 404


async def test_파티_글은_전체_커뮤니티_목록에_나오지_않는다(client, db_session):
    (a, ha), (b, hb), _ = await _setup(client, db_session)
    await client.post("/v1/parties/me/posts", json=POST, headers=ha)
    await client.post("/v1/community/posts", json={**POST, "title": "전체 글"}, headers=ha)
    titles = [i["title"] for i in (await client.get("/v1/community/posts", headers=hb)).json()["data"]["items"]]
    assert titles == ["전체 글"]
    party_titles = [i["title"] for i in (await client.get("/v1/parties/me/posts", headers=hb)).json()["data"]["items"]]
    assert party_titles == ["파티 글"]


async def test_파티를_나가면_그_파티_글은_안_보이고_파티가_없어지면_글도_지워진다(client, db_session):
    (a, ha), (b, hb), _ = await _setup(client, db_session)
    pid = (await client.post("/v1/parties/me/posts", json=POST, headers=ha)).json()["data"]["post_id"]
    await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "댓글"}, headers=hb)
    async with db_session() as s:
        await ps.leave(s, b)
    assert (await client.get(f"/v1/community/posts/{pid}", headers=hb)).status_code == 404   # 나간 사람은 못 본다
    assert (await client.get(f"/v1/community/posts/{pid}", headers=ha)).status_code == 200   # 남은 사람은 본다
    async with db_session() as s:
        await ps.leave(s, a)                                                                   # 마지막 한 명이 나가면
    async with db_session() as s:
        assert (await s.execute(select(CommunityPost))).scalars().all() == []
        assert (await s.execute(select(PieLedger).where(PieLedger.reason == "post_write"))).scalars().all() == []


async def test_파티가_없으면_파티_글을_못_쓴다(client, db_session):
    _, _, (c, hc) = await _setup(client, db_session)
    r = await client.post("/v1/parties/me/posts", json=POST, headers=hc)
    assert r.status_code == 404 and r.json()["error"]["code"] == "PARTY_NOT_JOINED"
