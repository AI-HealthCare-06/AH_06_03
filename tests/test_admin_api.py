"""관리자 최소 기능 테스트: 권한, 목록, 노출 스위치, 카테고리 순서, 안전장치."""
from datetime import date

import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User, UserProfile
from tests.conftest import make_user

pytestmark = pytest.mark.asyncio

ADMIN_EMAIL = "admin@test.kr"

SMOKER_DRINKER = {"SMOKING": "current", "ALCOHOL_FREQ": "2_3_per_week", "ALCOHOL_AMOUNT": "5_6",
                  "SBP": 145, "DBP": 92, "HEIGHT": 172, "WEIGHT": 78, "HTN_STATUS": "none", "DIABETES": "false"}
HIGH_NA = {"N0": ("salty", 50.0)} | {f"N{i}": ("very", 10.0) for i in range(1, 11)}
SURVEY = HIGH_NA | {"P1": ("none", None), "E1": ("rare", None), "B1": ("0", None)}

# 시드된 카테고리 순서(기본값)와 같은 순서여야 한다: 기본 동작이 바뀌지 않았다는 뜻
DEFAULT_ORDER = {"NA": 3, "ACT": 4, "OUT": 5, "BRK": 6, "WT": 7}


@pytest.fixture(autouse=True)
def admin_list(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", f" {ADMIN_EMAIL.upper()} , other@test.kr ")


async def make_account(Session, email: str, status: str = "active") -> dict:
    async with Session() as s:
        user = User(email=email, password_hash="x", status=status)
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        return {"Authorization": f"Bearer {create_access_token(user.user_id)}"}


async def catalog(client, h) -> dict:
    r = await client.get("/v1/admin/challenges", headers=h)
    assert r.status_code == 200, r.text
    return {c["category_code"]: c for c in r.json()["data"]}


async def mission(client, h, code: str) -> dict:
    for cat in (await catalog(client, h)).values():
        for m in cat["missions"]:
            if m["challenge_code"] == code:
                return m
    raise AssertionError(code)


async def candidates(client, user_h) -> list[str]:
    r = await client.get("/v1/challenges/recommendations", headers=user_h)
    assert r.status_code == 200, r.text
    return [c["code"] for c in r.json()["data"]["candidates"]]


# ---------------------------------------------------------------- 권한
async def test_login_required(client):
    r = await client.get("/v1/admin/challenges")
    assert r.status_code == 401


async def test_non_admin_forbidden(client, db_session):
    h = await make_account(db_session, "user@test.kr")
    r = await client.get("/v1/admin/challenges", headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "ADMIN_FORBIDDEN"


async def test_empty_list_means_nobody_is_admin(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "")
    h = await make_account(db_session, ADMIN_EMAIL)
    assert (await client.get("/v1/admin/challenges", headers=h)).status_code == 403


async def test_admin_email_is_case_insensitive_and_trimmed(client, db_session):
    h = await make_account(db_session, ADMIN_EMAIL)
    assert (await client.get("/v1/admin/challenges", headers=h)).status_code == 200


async def test_deleted_admin_is_forbidden(client, db_session):
    h = await make_account(db_session, ADMIN_EMAIL, status="deleted")
    assert (await client.get("/v1/admin/challenges", headers=h)).status_code == 403


async def test_non_admin_cannot_change_anything(client, db_session):
    admin = await make_account(db_session, ADMIN_EMAIL)
    user = await make_account(db_session, "user@test.kr")
    m = await mission(client, admin, "NA-1")
    r = await client.patch(f"/v1/admin/challenges/{m['challenge_id']}", json={"active": False}, headers=user)
    assert r.status_code == 403
    assert (await mission(client, admin, "NA-1"))["active"] is True


# ---------------------------------------------------------------- 목록
async def test_list_catalog_shape(client, db_session):
    h = await make_account(db_session, ADMIN_EMAIL)
    cats = await catalog(client, h)
    assert list(cats) == ["SMOKING", "ALCOHOL", "SODIUM", "ACTIVITY", "EATOUT", "BREAKFAST", "WEIGHT"]
    assert sum(len(c["missions"]) for c in cats.values()) == 10
    # 고정 미션과 고정 미션뿐인 카테고리는 스위치가 의미 없다고 알려 준다
    assert cats["SMOKING"]["switchable"] is False and cats["ALCOHOL"]["switchable"] is False
    assert cats["SODIUM"]["switchable"] is True
    assert (await mission(client, h, "SMK-1"))["switchable"] is False
    assert (await mission(client, h, "NA-1"))["switchable"] is True


# ---------------------------------------------------------------- 노출 스위치
async def test_mission_switch_changes_recommendations(client, db_session):
    admin = await make_account(db_session, ADMIN_EMAIL)
    user = await make_user(db_session, measurements=SMOKER_DRINKER, answers=SURVEY)
    assert "NA-1" in await candidates(client, user)

    na1 = await mission(client, admin, "NA-1")
    r = await client.patch(f"/v1/admin/challenges/{na1['challenge_id']}", json={"active": False}, headers=admin)
    assert r.status_code == 200 and r.json()["data"]["active"] is False
    after = await candidates(client, user)
    assert "NA-1" not in after and "BRK-1" in after  # 바로 반영, 다른 미션은 그대로

    r = await client.patch(f"/v1/admin/challenges/{na1['challenge_id']}", json={"active": True}, headers=admin)
    assert r.status_code == 200
    assert "NA-1" in await candidates(client, user)


async def test_category_switch_hides_all_its_missions(client, db_session):
    admin = await make_account(db_session, ADMIN_EMAIL)
    user = await make_user(db_session, measurements=SMOKER_DRINKER, answers=SURVEY)
    sodium = (await catalog(client, admin))["SODIUM"]
    r = await client.patch(f"/v1/admin/challenge-categories/{sodium['category_id']}", json={"active": False}, headers=admin)
    assert r.status_code == 200 and r.json()["data"]["active"] is False
    codes = await candidates(client, user)
    assert "NA-1" not in codes and "NA-2" not in codes and "BRK-1" in codes


async def test_fixed_missions_cannot_be_switched(client, db_session):
    admin = await make_account(db_session, ADMIN_EMAIL)
    smk = await mission(client, admin, "SMK-1")
    r = await client.patch(f"/v1/admin/challenges/{smk['challenge_id']}", json={"active": False}, headers=admin)
    assert r.status_code == 422 and r.json()["error"]["code"] == "ADMIN_NOT_SWITCHABLE"
    assert (await mission(client, admin, "SMK-1"))["active"] is True
    cat = (await catalog(client, admin))["SMOKING"]
    r = await client.patch(f"/v1/admin/challenge-categories/{cat['category_id']}", json={"active": False}, headers=admin)
    assert r.status_code == 422 and r.json()["error"]["code"] == "ADMIN_NOT_SWITCHABLE"


async def test_last_selectable_mission_cannot_be_turned_off(client, db_session):
    admin = await make_account(db_session, ADMIN_EMAIL)
    selectable = [m for c in (await catalog(client, admin)).values() for m in c["missions"] if m["switchable"]]
    assert len(selectable) == 8
    for m in selectable[:-1]:
        r = await client.patch(f"/v1/admin/challenges/{m['challenge_id']}", json={"active": False}, headers=admin)
        assert r.status_code == 200
    last = selectable[-1]
    r = await client.patch(f"/v1/admin/challenges/{last['challenge_id']}", json={"active": False}, headers=admin)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ADMIN_LAST_SELECTABLE"
    assert (await mission(client, admin, last["challenge_code"]))["active"] is True  # 거절하면 그대로


async def test_last_selectable_category_cannot_be_turned_off(client, db_session):
    admin = await make_account(db_session, ADMIN_EMAIL)
    cats = await catalog(client, admin)
    codes = ["SODIUM", "ACTIVITY", "EATOUT", "BREAKFAST"]
    for code in codes:
        r = await client.patch(f"/v1/admin/challenge-categories/{cats[code]['category_id']}", json={"active": False}, headers=admin)
        assert r.status_code == 200
    r = await client.patch(f"/v1/admin/challenge-categories/{cats['WEIGHT']['category_id']}", json={"active": False}, headers=admin)
    assert r.status_code == 409
    assert (await catalog(client, admin))["WEIGHT"]["active"] is True


# ---------------------------------------------------------------- 순서
async def test_default_order_is_unchanged_and_admin_order_is_applied(client, db_session):
    admin = await make_account(db_session, ADMIN_EMAIL)
    user = await make_user(db_session, measurements=SMOKER_DRINKER, answers=SURVEY)

    before = await candidates(client, user)
    assert "WT-1" in before and before[0] != "WT-1"
    # 기본 순서는 카테고리 기본 순서와 같다 (이번 변경이 기본 동작을 바꾸지 않음)
    assert before == sorted(before, key=lambda c: DEFAULT_ORDER[c.split("-")[0]])

    weight = (await catalog(client, admin))["WEIGHT"]
    r = await client.patch(f"/v1/admin/challenge-categories/{weight['category_id']}", json={"display_order": 0}, headers=admin)
    assert r.status_code == 200 and r.json()["data"]["display_order"] == 0
    after = await candidates(client, user)
    assert after[0] == "WT-1" and sorted(after) == sorted(before)  # 맨 위로, 후보 구성은 그대로
    cats = await catalog(client, admin)
    assert list(cats)[0] == "WEIGHT"  # 관리자 목록도 새 순서


# ---------------------------------------------------------------- 입력 검사
async def test_patch_validation(client, db_session):
    admin = await make_account(db_session, ADMIN_EMAIL)
    cat = (await catalog(client, admin))["SODIUM"]
    url = f"/v1/admin/challenge-categories/{cat['category_id']}"
    assert (await client.patch(url, json={}, headers=admin)).status_code == 422
    assert (await client.patch(url, json={"display_order": 100}, headers=admin)).status_code == 422
    assert (await client.patch(url, json={"display_order": -1}, headers=admin)).status_code == 422
    assert (await client.patch(url, json={"name": "x"}, headers=admin)).status_code == 422
    m = await mission(client, admin, "NA-1")
    assert (await client.patch(f"/v1/admin/challenges/{m['challenge_id']}", json={}, headers=admin)).status_code == 422


async def test_unknown_ids_are_404(client, db_session):
    admin = await make_account(db_session, ADMIN_EMAIL)
    r = await client.patch("/v1/admin/challenges/nope", json={"active": False}, headers=admin)
    assert r.status_code == 404
    r = await client.patch("/v1/admin/challenge-categories/nope", json={"active": False}, headers=admin)
    assert r.status_code == 404
