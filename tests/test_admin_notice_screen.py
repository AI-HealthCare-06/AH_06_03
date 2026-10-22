"""관리자 화면의 공지 탭이 보내는 요청 모양 그대로 서버가 처리하는지 (한국 시각 +09:00 → UTC 저장, 수정, 지금 내리기)."""
import pytest

from tests.test_notices import admin_list, make_account, public_titles  # noqa: F401 (admin_list는 자동 적용 픽스처)

pytestmark = pytest.mark.asyncio


async def test_공지_탭에서_한국_시각으로_올리고_고치고_내린다(client, db_session):
    h = await make_account(db_session, "admin@test.kr")
    # 화면: 시작은 비우고(지금부터), 끝은 한국 시각 2099-10-25 23:59 → "2099-10-25T23:59:00+09:00"
    r = await client.post("/v1/admin/notices", headers=h, json={
        "title": "체험 안내", "body": "참여해 주셔서 감사해요.\n체험은 25일까지예요.", "ends_at": "2099-10-25T23:59:00+09:00"})
    assert r.status_code == 201, r.text
    n = r.json()["data"]
    assert n["ends_at"].startswith("2099-10-25T14:59")          # UTC로 저장(한국 시각 - 9시간)
    assert n["status"] == "active"
    assert "체험 안내" in await public_titles(client)            # 이용자 화면에 바로 보임

    # 화면: 목록 불러오기
    r = await client.get("/v1/admin/notices?limit=50", headers=h)
    assert [x["title"] for x in r.json()["data"]] == ["체험 안내"]

    # 화면: 수정에서 바뀐 칸만 보냄
    url = f"/v1/admin/notices/{n['notice_id']}"
    r = await client.patch(url, headers=h, json={"title": "체험 안내(수정)", "ends_at": "2099-10-26T09:00:00+09:00"})
    assert r.status_code == 200 and r.json()["data"]["ends_at"].startswith("2099-10-26T00:00")

    # 화면: 지금 내리기
    r = await client.patch(url, headers=h, json={"end_now": True})
    assert r.status_code == 200 and r.json()["data"]["status"] == "ended"
    assert "체험 안내(수정)" not in await public_titles(client)


async def test_끝이_시작보다_앞이면_화면에_오류가_간다(client, db_session):
    h = await make_account(db_session, "admin@test.kr")
    r = await client.post("/v1/admin/notices", headers=h, json={
        "title": "잘못된 기간", "body": "본문", "starts_at": "2099-10-25T10:00:00+09:00", "ends_at": "2099-10-25T09:00:00+09:00"})
    assert r.status_code == 422
