"""가입 동의 검사: 화면이 보낸 정책 ID·버전·체크 값을 서버가 확인하고, 그대로 기록한다."""
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.consent import ConsentPolicy, UserConsent
from app.models.user import User

pytestmark = pytest.mark.asyncio

TYPES = ("terms_of_service", "privacy", "health_data")


async def seed_policies(Session, version="v1") -> dict:
    ids = {}
    async with Session() as s:
        for t in TYPES:
            p = ConsentPolicy(policy_type=t, version=version, purpose_text="a", collection_items="b", retention_policy="c",
                              withdrawal_method="d", third_party_notice="e", published_at=datetime(2026, 10, 1))
            s.add(p)
            await s.flush()
            ids[t] = p.policy_id
        await s.commit()
    return ids


def body(ids, version="v1", **over):
    consents = [{"policy_id": ids[t], "version": version, "agreed": True} for t in TYPES]
    return {"email": "a@test.kr", "password": "password1", "birth_date": "1985-05-05", "consents": consents, **over}


async def test_signup_records_what_was_sent(client, db_session):
    ids = await seed_policies(db_session)
    r = await client.post("/v1/auth/signup", json=body(ids))
    assert r.status_code == 201, r.text
    async with db_session() as s:
        rows = (await s.execute(select(UserConsent))).scalars().all()
    assert sorted(c.policy_id for c in rows) == sorted(ids.values()) and all(c.status == "agreed" for c in rows)


async def test_signup_without_consents_is_rejected(client, db_session):
    await seed_policies(db_session)
    b = {"email": "a@test.kr", "password": "password1", "birth_date": "1985-05-05"}
    assert (await client.post("/v1/auth/signup", json=b)).status_code == 422


@pytest.mark.parametrize("drop", ["agreed_false", "missing"])
async def test_signup_needs_every_policy_agreed(client, db_session, drop):
    ids = await seed_policies(db_session)
    b = body(ids)
    if drop == "agreed_false":
        b["consents"][2]["agreed"] = False
    else:
        b["consents"].pop()
    r = await client.post("/v1/auth/signup", json=b)
    assert r.status_code == 422 and r.json()["error"]["code"] == "CONSENT_REQUIRED"
    async with db_session() as s:
        assert (await s.execute(select(User))).scalars().all() == []     # 계정도 만들어지지 않는다


async def test_signup_with_outdated_policy_is_conflict(client, db_session):
    ids = await seed_policies(db_session)
    r = await client.post("/v1/auth/signup", json=body(ids, version="v0"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONSENT_POLICY_OUTDATED"
    b = body(ids)
    b["consents"][0]["policy_id"] = "00000000-0000-0000-0000-000000000000"
    assert (await client.post("/v1/auth/signup", json=b)).status_code == 409
