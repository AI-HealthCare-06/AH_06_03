"""신고 누적으로 자동 숨김되는 순간 관리자에게 디스코드 알림을 한 번 보내고, 관리자 기록에 남긴다. 내용·작성자는 넣지 않는다."""
import asyncio
from datetime import date

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.admin_audit import AdminAuditLog
from app.models.user import User, UserProfile
from app.services import admin_alert

pytestmark = pytest.mark.asyncio

TITLE, BODY, NICK = "아주 특이한 제목", "아주 특이한 본문", "글쓴고양이"


async def make(client, Session, email: str, nick: str | None = None) -> dict:
    async with Session() as s:
        user = User(email=email, password_hash="x", status="active")
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        h = {"Authorization": f"Bearer {create_access_token(user.user_id)}"}
    if nick:
        await client.put("/v1/community/me", json={"nickname": nick}, headers=h)
    return h


@pytest.fixture
def sent(monkeypatch):
    """보낸 알림 문구를 모은다 (실제로 디스코드에 보내지 않음)."""
    box: list[str] = []
    monkeypatch.setattr(admin_alert, "notify", box.append)
    return box


async def test_3명째_신고로_숨겨질_때_한_번만_알린다(client, db_session, sent):
    author = await make(client, db_session, "w@test.kr", NICK)
    r = [await make(client, db_session, f"r{i}@test.kr", f"신고자{i}") for i in range(4)]
    pid = (await client.post("/v1/community/posts", json={"category": "tips", "title": TITLE, "body": BODY},
                             headers=author)).json()["data"]["post_id"]
    for i in range(2):
        await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "abuse"}, headers=r[i])
    assert sent == []                                                    # 2명까지는 알림 없음
    await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "abuse"}, headers=r[2])
    assert len(sent) == 1 and "글 1건" in sent[0] and "자동 숨김" in sent[0]
    assert all(x not in sent[0] for x in (TITLE, BODY, NICK, pid))      # 내용·작성자·번호는 안 보낸다


async def test_댓글이_숨겨질_때도_알린다(client, db_session, sent):
    author = await make(client, db_session, "w@test.kr", NICK)
    r = [await make(client, db_session, f"r{i}@test.kr", f"신고자{i}") for i in range(3)]
    pid = (await client.post("/v1/community/posts", json={"category": "tips", "title": "글", "body": "x"},
                             headers=author)).json()["data"]["post_id"]
    cid = (await client.post(f"/v1/community/posts/{pid}/comments", json={"body": "댓글"}, headers=author)).json()["data"]["comment_id"]
    for h in r:
        await client.post(f"/v1/community/comments/{cid}/report", json={"reason": "spam"}, headers=h)
    assert len(sent) == 1 and "댓글 1건" in sent[0]


async def test_웹후크가_비어_있으면_아무것도_보내지_않는다(monkeypatch):
    called = []
    monkeypatch.setattr(settings, "ADMIN_ALERT_WEBHOOK", "")
    monkeypatch.setattr(admin_alert, "_post", lambda text: called.append(text))
    admin_alert.notify("시험")
    assert called == []


async def test_웹후크가_있으면_백그라운드로_보낸다(monkeypatch):
    got = []

    async def fake_post(text):
        got.append(text)

    monkeypatch.setattr(settings, "ADMIN_ALERT_WEBHOOK", "https://example.invalid/hook")
    monkeypatch.setattr(admin_alert, "_post", fake_post)
    admin_alert.notify("시험")
    await asyncio.sleep(0)
    assert got == ["시험"]


async def test_보내기에_실패해도_오류가_밖으로_나오지_않는다(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ADMIN_ALERT_WEBHOOK", "http://127.0.0.1:9/secret-hook")   # 닫힌 포트
    await admin_alert._post("시험")                                     # 예외 없이 끝나야 함
    assert "secret-hook" not in caplog.text                             # 로그에 웹후크 주소가 남지 않음


async def test_자동_숨김은_관리자_기록에_시스템으로_남는다(client, db_session, sent):
    author = await make(client, db_session, "w@test.kr", NICK)
    r = [await make(client, db_session, f"r{i}@test.kr", f"신고자{i}") for i in range(4)]
    pid = (await client.post("/v1/community/posts", json={"category": "tips", "title": TITLE, "body": BODY},
                             headers=author)).json()["data"]["post_id"]
    for h in r:                                                          # 4명째 신고는 이미 숨겨져서 404, 기록도 한 번만
        await client.post(f"/v1/community/posts/{pid}/report", json={"reason": "abuse"}, headers=h)
    async with db_session() as s:
        logs = (await s.execute(select(AdminAuditLog.actor_email, AdminAuditLog.action, AdminAuditLog.target,
                                       AdminAuditLog.detail))).all()
    assert logs == [("system(신고 누적)", "community_auto_hide", f"p-{pid[-8:]}", "신고 3명")]
    assert all(TITLE not in (t or "") + (d or "") for _, _, t, d in logs)
