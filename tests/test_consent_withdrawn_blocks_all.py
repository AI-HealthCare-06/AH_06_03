"""건강정보 동의를 철회하면 로그인이 남아 있어도 서비스(커뮤니티·파이·캐릭터·공통 챌린지 포함)를 쓸 수 없다.
계정 보기, 동의 다시 하기, 내 데이터 내려받기, 탈퇴, 공지·문의는 그대로 쓸 수 있다 (팀 결정: 철회하면 모든 서비스 이용 불가)."""
from datetime import date

import pytest

from app.core.security import create_access_token, utcnow
from app.models.consent import ConsentPolicy, UserConsent
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio

BLOCKED = ["/v1/community/posts", "/v1/community/me", "/v1/pie", "/v1/pie/history",
           "/v1/characters/me", "/v1/characters/items", "/v1/common-challenges"]
OPEN = ["/v1/users/me", "/v1/users/me/consents", "/v1/consent-policies/active", "/v1/users/me/data-export"]


async def _withdrawn_user(Session) -> dict:
    async with Session() as s:
        u = User(email="w@test.kr", password_hash="x", status="active")
        s.add(u)
        await s.flush()
        s.add(UserProfile(user_id=u.user_id, sex="male", birth_date=date(1981, 3, 1)))
        now = utcnow()
        health = ConsentPolicy(policy_type="health_data", version="v4", purpose_text="a", collection_items="b",
                               retention_policy="c", withdrawal_method="d", third_party_notice="e", published_at=now)
        s.add(health)
        await s.flush()
        s.add(UserConsent(user_id=u.user_id, policy_id=health.policy_id, status="withdrawn", consented_at=now, withdrawn_at=now))
        await s.commit()
        return {"Authorization": f"Bearer {create_access_token(u.user_id)}"}


async def test_철회하면_커뮤니티_파이_캐릭터_공통챌린지를_막는다(client, db_session):
    h = await _withdrawn_user(db_session)
    for path in BLOCKED:
        r = await client.get(path, headers=h)
        assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_WITHDRAWN", path


async def test_철회해도_계정_동의_내려받기는_쓸_수_있다(client, db_session):
    h = await _withdrawn_user(db_session)
    for path in OPEN:
        assert (await client.get(path, headers=h)).status_code == 200, path