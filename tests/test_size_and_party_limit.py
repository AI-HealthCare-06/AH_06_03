"""API 보안 검사 4묶음: 큰 사진 본문을 통째로 읽지 않기, 파티 초대 코드 대입 막기."""
import pytest

from app.core.errors import AppError
from app.core.security import create_access_token
from app.services import party_service as ps
from tests.test_parties import _party, _user

pytestmark = pytest.mark.asyncio
POST = {"category": "tips", "title": "사진 글", "body": "본문"}


async def auth(uid: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(uid)}"}


async def my_post(client, db_session) -> tuple[str, dict]:
    uid = await _user(db_session, "photo@test.kr")
    h = await auth(uid)
    await client.put("/v1/community/me", json={"nickname": "사진쟁이"}, headers=h)
    pid = (await client.post("/v1/community/posts", json=POST, headers=h)).json()["data"]["post_id"]
    return pid, h


async def test_크기가_큰_사진은_길이만_보고_바로_거절한다(client, db_session):
    pid, h = await my_post(client, db_session)
    big = b"\xff\xd8\xff" + b"0" * (400 * 1024)
    r = await client.post(f"/v1/community/posts/{pid}/photos", content=big,
                          headers={**h, "Content-Type": "image/jpeg"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "PHOTO_TOO_LARGE"


async def test_길이를_밝히지_않은_큰_본문도_300KB에서_읽기를_멈춘다(client, db_session):
    pid, h = await my_post(client, db_session)
    read = {"n": 0}

    async def chunks():                                                  # 길이 머리말 없이 조각으로 보내는 본문
        for _ in range(50):                                              # 50 × 64KB = 3.2MB
            read["n"] += 1
            yield b"0" * (64 * 1024)

    r = await client.post(f"/v1/community/posts/{pid}/photos", content=chunks(),
                          headers={**h, "Content-Type": "image/jpeg"})
    assert r.status_code == 413
    assert read["n"] < 50                                                # 끝까지 읽지 않고 멈췄다


async def test_초대_코드를_10번_틀리면_맞는_코드도_잠시_막힌다(client, db_session):
    owner = await _user(db_session, "owner@test.kr")
    party = await _party(db_session, owner)
    guesser = await auth(await _user(db_session, "guesser@test.kr"))
    for i in range(ps.JOIN_FAIL_MAX):
        r = await client.post("/v1/parties/join", json={"invite_code": f"PAEON-ZZZ{i % 10}"}, headers=guesser)
        assert r.status_code == 404
    r = await client.post("/v1/parties/join", json={"invite_code": party.invite_code}, headers=guesser)
    assert r.status_code == 429 and r.json()["error"]["code"] == "PARTY_JOIN_TOO_MANY"
    friend = await auth(await _user(db_session, "friend@test.kr"))       # 다른 사람은 그대로 들어갈 수 있다
    assert (await client.post("/v1/parties/join", json={"invite_code": party.invite_code}, headers=friend)).status_code in (200, 201)


async def test_한두_번_틀린_뒤_맞는_코드로는_들어갈_수_있다(db_session):
    owner = await _user(db_session, "o2@test.kr")
    party = await _party(db_session, owner)
    uid = await _user(db_session, "u2@test.kr")
    async with db_session() as s:
        for _ in range(2):
            with pytest.raises(AppError):
                await ps.join(s, uid, "PAEON-0000")
        info = await ps.join(s, uid, party.invite_code)
    assert info.party_id == party.party_id
    assert uid not in ps._join_failures                                 # 들어가면 틀린 횟수는 지운다
