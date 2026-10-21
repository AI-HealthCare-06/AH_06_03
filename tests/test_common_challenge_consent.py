"""건강정보 동의를 철회하면 공통 챌린지도 쓸 수 없다 (멘토링 10/20 지적). 개인 챌린지·파티와 같은 기준."""
import pytest

from tests.test_signup_consent import body, seed_policies

pytestmark = pytest.mark.asyncio
EMAIL, PW = "cc@test.kr", "password1"


async def signed_up(client, db_session) -> tuple[dict, dict]:
    ids = await seed_policies(db_session)
    assert (await client.post("/v1/auth/signup", json=body(ids, email=EMAIL, password=PW))).status_code == 201
    tok = (await client.post("/v1/auth/login", json={"email": EMAIL, "password": PW})).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {tok}"}, ids


async def test_동의를_철회하면_공통_챌린지_참여와_인증이_막힌다(client, db_session):
    h, ids = await signed_up(client, db_session)
    assert (await client.get("/v1/common-challenges", headers=h)).status_code == 200      # 동의 상태에서는 그대로
    assert (await client.delete(f"/v1/users/me/consents/{ids['health_data']}", headers=h)).status_code == 200
    calls = [("GET", "/v1/common-challenges"), ("GET", "/v1/common-challenges/x"),
             ("POST", "/v1/common-challenges/x/join"), ("POST", "/v1/common-challenges/x/certify")]
    for method, url in calls:
        r = await client.request(method, url, headers=h, json={} if method == "POST" else None)
        assert r.status_code == 403 and r.json()["error"]["code"] == "CONSENT_WITHDRAWN", (method, url)


async def test_다시_동의하면_공통_챌린지를_쓸_수_있다(client, db_session):
    h, ids = await signed_up(client, db_session)
    await client.delete(f"/v1/users/me/consents/{ids['health_data']}", headers=h)
    assert (await client.post("/v1/users/me/consents", json={"policy_id": ids["health_data"]}, headers=h)).status_code == 200
    assert (await client.get("/v1/common-challenges", headers=h)).status_code == 200
