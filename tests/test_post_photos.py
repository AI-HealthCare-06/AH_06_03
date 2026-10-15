"""글 사진: JPEG만, 한 장 300KB 이하, 글당 3장, 촬영 위치(GPS)가 있으면 거절, 숨김·파티 글의 사진은 볼 수 있는 사람에게만."""
import struct

import pytest
from sqlalchemy import select

from app.apis.consent import require_health_consent
from app.main import app
from app.models.community import CommunityPost, CommunityPostPhoto
from app.services import party_service as ps
from tests.test_community import with_nick

pytestmark = pytest.mark.asyncio


def jpeg(extra: bytes = b"") -> bytes:
    """읽을 수 있는 그림이 아니라 JPEG 머리 부분만 흉내 낸 시험용 바이트 (서버는 머리 부분만 본다)."""
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + extra + b"\xff\xd9"


def exif_jpeg(with_gps: bool) -> bytes:
    """EXIF(APP1)가 들어 있는 시험용 JPEG. with_gps면 IFD0에 GPS 가리킴(0x8825) 항목이 있다."""
    tag = 0x8825 if with_gps else 0x010F
    entry = struct.pack("<HHII", tag, 4, 1, 0)
    tiff = b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", 1) + entry + struct.pack("<I", 0)
    body = b"Exif\x00\x00" + tiff
    return b"\xff\xd8\xff\xe1" + struct.pack(">H", len(body) + 2) + body + b"\xff\xd9"


@pytest.fixture(autouse=True)
def consent_ok():
    app.dependency_overrides[require_health_consent] = lambda: None
    yield
    app.dependency_overrides.pop(require_health_consent, None)


async def new_post(client, h, title="사진 글"):
    r = await client.post("/v1/community/posts", json={"category": "tips", "title": title, "body": "본문"}, headers=h)
    return r.json()["data"]["post_id"]


async def up(client, h, pid, data):
    return await client.post(f"/v1/community/posts/{pid}/photos", content=data,
                             headers={**h, "Content-Type": "image/jpeg"})


async def test_사진을_올리고_받고_목록에는_개수만_나온다(client, db_session):
    _, h = await with_nick(client, db_session, "a@t.kr", "가가")
    pid = await new_post(client, h)
    assert (await up(client, h, pid, jpeg())).json()["data"]["position"] == 0
    assert (await up(client, h, pid, jpeg(b"2"))).json()["data"]["position"] == 1
    got = await client.get(f"/v1/community/posts/{pid}/photos/1", headers=h)
    assert got.status_code == 200 and got.headers["content-type"] == "image/jpeg" and got.content == jpeg(b"2")
    item = (await client.get("/v1/community/posts", headers=h)).json()["data"]["items"][0]
    assert item["photo_count"] == 2 and "photo" not in item            # 목록에는 개수만, 사진 자체는 실리지 않는다
    assert (await client.get(f"/v1/community/posts/{pid}", headers=h)).json()["data"]["photo_count"] == 2


async def test_JPEG가_아니거나_크거나_위치가_있거나_4장째면_거절한다(client, db_session):
    _, h = await with_nick(client, db_session, "a@t.kr", "가가")
    pid = await new_post(client, h)
    r = await up(client, h, pid, b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    assert r.status_code == 415 and r.json()["error"]["code"] == "PHOTO_NOT_JPEG"
    r = await up(client, h, pid, jpeg(b"0" * (300 * 1024)))
    assert r.status_code == 413 and r.json()["error"]["code"] == "PHOTO_TOO_LARGE"
    r = await up(client, h, pid, exif_jpeg(with_gps=True))
    assert r.status_code == 400 and r.json()["error"]["code"] == "PHOTO_HAS_LOCATION"
    assert (await up(client, h, pid, exif_jpeg(with_gps=False))).status_code == 201     # EXIF가 있어도 위치만 없으면 된다
    for i in range(2):
        assert (await up(client, h, pid, jpeg(bytes([i])))).status_code == 201
    r = await up(client, h, pid, jpeg())
    assert r.status_code == 409 and r.json()["error"]["code"] == "PHOTO_LIMIT"


async def test_남의_글에는_올릴_수_없다(client, db_session):
    _, ha = await with_nick(client, db_session, "a@t.kr", "가가")
    _, hb = await with_nick(client, db_session, "b@t.kr", "나나")
    pid = await new_post(client, ha)
    assert (await up(client, hb, pid, jpeg())).status_code == 404


async def test_숨김_처리된_글의_사진은_작성자만_받는다(client, db_session):
    _, ha = await with_nick(client, db_session, "a@t.kr", "가가")
    _, hb = await with_nick(client, db_session, "b@t.kr", "나나")
    pid = await new_post(client, ha)
    await up(client, ha, pid, jpeg())
    assert (await client.get(f"/v1/community/posts/{pid}/photos/0", headers=hb)).status_code == 200
    async with db_session() as s:
        (await s.get(CommunityPost, pid)).status = "hidden"
        await s.commit()
    assert (await client.get(f"/v1/community/posts/{pid}/photos/0", headers=hb)).status_code == 404
    assert (await client.get(f"/v1/community/posts/{pid}/photos/0", headers=ha)).status_code == 200


async def test_파티_글의_사진은_파티원만_받고_글을_지우면_사진도_사라진다(client, db_session):
    a, ha = await with_nick(client, db_session, "a@t.kr", "가가")
    b, hb = await with_nick(client, db_session, "b@t.kr", "나나")
    _, hc = await with_nick(client, db_session, "c@t.kr", "다다")
    async with db_session() as s:
        info = await ps.create(s, a, "아침걷기", None, (await ps.challenge_options(s))[0].challenge_code)
    async with db_session() as s:
        await ps.join(s, b, info.invite_code)
    r = await client.post("/v1/parties/me/posts", json={"category": "tips", "title": "t", "body": "파티 글"}, headers=ha)
    pid = r.json()["data"]["post_id"]
    await up(client, ha, pid, jpeg())
    assert (await client.get(f"/v1/community/posts/{pid}/photos/0", headers=hb)).status_code == 200
    assert (await client.get(f"/v1/community/posts/{pid}/photos/0", headers=hc)).status_code == 404
    assert (await client.delete(f"/v1/community/posts/{pid}", headers=ha)).status_code == 204
    async with db_session() as s:
        assert (await s.execute(select(CommunityPostPhoto))).scalars().all() == []
