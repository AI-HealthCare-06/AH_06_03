"""관리자 운영 현황 테스트: 진행 단계별 인원, 동의·삭제 현황, 서비스 상태, 집계 CSV, 권한, 개인 식별 정보 없음, 열람·내려받기 기록."""
import csv
import io
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, utcnow
from app.models.access_log import AccessLog
from app.models.admin_audit import AdminAuditLog
from app.models.challenge import ChallengeCycle
from app.models.consent import ConsentPolicy, UserConsent
from app.models.deletion import AccountDeletionRequest
from app.models.eligibility import EligibilityAssessment
from app.models.health import HealthRecord
from app.models.prediction import Prediction
from app.models.survey import SurveyInstance, SurveyVersion
from app.models.user import User, UserProfile

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 10, 12, 9, 0)


@pytest.fixture(autouse=True)
def wired(monkeypatch):
    """main.py에 연결되기 전에도 시험이 돌도록, 아직 없으면 이 라우터를 앱에 붙인다."""
    from app.apis.admin_overview import router
    from app.main import app
    if not any(getattr(r, "path", "") == "/v1/admin/overview" for r in app.routes):
        app.include_router(router, prefix="/v1")
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@test.kr")


async def make_account(Session, email: str, status: str = "active") -> tuple[dict, str]:
    async with Session() as s:
        user = User(email=email, password_hash="x", status=status)
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex="male", birth_date=date(1981, 3, 1)))
        await s.commit()
        return {"Authorization": f"Bearer {create_access_token(user.user_id)}"}, user.user_id


@pytest_asyncio.fixture
async def seeded(db_session):
    """사용자 7명이 단계별로 멈춘 상태 + 탈퇴 1명 + 동의·삭제 기록."""
    ids = []
    for n in range(7):
        _, uid = await make_account(db_session, f"u{n}@test.kr")
        ids.append(uid)
    _, gone = await make_account(db_session, "gone@test.kr", status="deleted")
    async with db_session() as s:
        for uid in ids[1:]:                                           # u1~u6 대상 확인
            s.add(EligibilityAssessment(user_id=uid, result_code="eligible", age_eligible=True, diagnosed_cad=False,
                                        emergency_flag=False, assessed_at=NOW))
        for uid in ids[2:]:                                           # u2~u6 건강정보
            s.add(HealthRecord(user_id=uid, health_schema_id="schema-1", input_type="initial",
                               examination_date=date(2026, 10, 8), created_at=NOW))
        ver = SurveyVersion(survey_type="initial_lifestyle", version="t1", active_from=NOW)
        s.add(ver)
        await s.flush()
        for uid in ids[3:]:                                           # u3~u6 설문 제출
            s.add(SurveyInstance(user_id=uid, survey_version_id=ver.survey_version_id, status="submitted",
                                 started_at=NOW, submitted_at=NOW))
        s.add(SurveyInstance(user_id=ids[2], survey_version_id=ver.survey_version_id, status="abandoned", started_at=NOW))
        for n, uid in enumerate(ids[4:]):                             # u4~u6 분석 결과 (u3은 건너뜀 상태라 안 센다)
            s.add(Prediction(prediction_job_id=f"job{n}", user_id=uid, model_code="MODEL_A", status="completed", predicted_at=NOW))
        s.add(Prediction(prediction_job_id="job-skip", user_id=ids[3], model_code="MODEL_A", status="skipped",
                         skip_reason="age_out_of_range", predicted_at=NOW))
        for number, (uid, status) in enumerate([(ids[5], "active"), (ids[6], "completed")], start=1):
            s.add(ChallengeCycle(user_id=uid, cycle_number=number, started_on=date(2026, 9, 1), ended_on=date(2026, 9, 28),
                                 status=status, created_at=NOW, updated_at=NOW))
        terms = ConsentPolicy(policy_type="terms_of_service", version="v1", purpose_text="a", collection_items="b",
                              retention_policy="c", withdrawal_method="d", third_party_notice="e", published_at=NOW)
        health = ConsentPolicy(policy_type="health_data", version="v4", purpose_text="a", collection_items="b",
                               retention_policy="c", withdrawal_method="d", third_party_notice="e", published_at=NOW)
        s.add_all([terms, health])
        await s.flush()
        for uid in ids[:3]:
            s.add(UserConsent(user_id=uid, policy_id=terms.policy_id, status="agreed", consented_at=NOW))
        s.add(UserConsent(user_id=ids[1], policy_id=health.policy_id, status="agreed", consented_at=NOW))
        s.add(UserConsent(user_id=ids[2], policy_id=health.policy_id, status="withdrawn", consented_at=NOW, withdrawn_at=NOW))
        s.add(AccountDeletionRequest(user_id=gone, reauthenticated_at=NOW, requested_at=NOW, status="completed", completed_at=NOW,
                                     result_summary={"predictions": 2, "user_consents": 3, "calendar_entries": 3}))
        s.add(AccountDeletionRequest(user_id=gone, reauthenticated_at=NOW, requested_at=NOW, status="failed",
                                     result_summary={"predictions": 99}))
        await s.commit()


async def overview(client, h) -> dict:
    r = await client.get("/v1/admin/overview", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def test_requires_admin(client, db_session):
    assert (await client.get("/v1/admin/overview")).status_code == 401
    assert (await client.get("/v1/admin/overview/export.csv")).status_code == 401
    h, _ = await make_account(db_session, "user@test.kr")
    for path in ("/v1/admin/overview", "/v1/admin/overview/export.csv"):
        r = await client.get(path, headers=h)
        assert r.status_code == 403 and r.json()["error"]["code"] == "ADMIN_FORBIDDEN"


async def test_funnel_counts_each_stage(client, db_session, seeded):
    h, _ = await make_account(db_session, "admin@test.kr")
    d = await overview(client, h)
    f = {s["code"]: s for s in d["funnel"]}
    # 가입 8명(운영자 포함, 탈퇴 1명은 안 셈)
    assert [(s["code"], s["users"]) for s in d["funnel"]] == [
        ("signup", 8), ("eligibility", 6), ("health", 5), ("survey", 4), ("prediction", 3),
        ("challenge_started", 2), ("challenge_completed", 1)]
    assert f["signup"]["rate_of_previous"] is None
    assert f["eligibility"]["rate_of_signup"] == 0.75 and f["eligibility"]["rate_of_previous"] == 0.75
    assert f["health"]["rate_of_previous"] == 0.833 and f["survey"]["rate_of_previous"] == 0.8
    assert f["challenge_completed"]["rate_of_previous"] == 0.5


async def test_funnel_counts_later_stage_as_passed(client, db_session):
    """대상 확인 저장 전에 가입해 그 기록 없이 건강정보로 넘어간 사람도 대상 확인을 지난 것으로 센다.
    아래 단계가 위 단계보다 많아지면(앞 단계 대비 100% 초과) 안 된다. 활성이 아닌 계정의 기록은 세지 않는다."""
    h, _ = await make_account(db_session, "admin@test.kr")
    _, new_user = await make_account(db_session, "new@test.kr")
    _, old1 = await make_account(db_session, "old1@test.kr")
    _, old2 = await make_account(db_session, "old2@test.kr")
    _, waiting = await make_account(db_session, "waiting@test.kr", status="pending_guardian")
    async with db_session() as s:
        s.add(EligibilityAssessment(user_id=new_user, result_code="eligible", age_eligible=True, diagnosed_cad=False,
                                    emergency_flag=False, assessed_at=NOW))
        for uid in (old1, old2, waiting):                             # 대상 확인 기록 없이 건강정보만
            s.add(HealthRecord(user_id=uid, health_schema_id="schema-1", input_type="initial",
                               examination_date=date(2026, 10, 8), created_at=NOW))
        s.add(Prediction(prediction_job_id="job-old1", user_id=old1, model_code="MODEL_B", status="completed",
                         predicted_at=NOW))                           # old1은 설문을 건너뛰고 분석까지
        await s.commit()
    d = await overview(client, h)
    assert [(s["code"], s["users"]) for s in d["funnel"]] == [
        ("signup", 4), ("eligibility", 3), ("health", 2), ("survey", 1), ("prediction", 1),
        ("challenge_started", 0), ("challenge_completed", 0)]
    assert {s["code"]: s["label"] for s in d["funnel"]}["survey"] == "설문 단계"
    assert all(s["rate_of_previous"] is None or s["rate_of_previous"] <= 1 for s in d["funnel"])


async def test_funnel_without_data_has_no_rates(client, db_session):
    h, _ = await make_account(db_session, "admin@test.kr")
    d = await overview(client, h)
    assert [s["users"] for s in d["funnel"]] == [1, 0, 0, 0, 0, 0, 0]       # 가입은 관리자 본인 1명
    assert d["funnel"][1]["rate_of_previous"] == 0.0


async def test_consent_and_deletion_status(client, db_session, seeded):
    h, _ = await make_account(db_session, "admin@test.kr")
    d = await overview(client, h)
    assert {(c["policy_type"], c["version"]): (c["agreed"], c["withdrawn"]) for c in d["consents"]} == {
        ("health_data", "v4"): (1, 1), ("terms_of_service", "v1"): (3, 0)}
    dele = d["deletions"]
    assert dele["deleted_accounts"] == 1 and dele["consent_withdrawals"] == 1
    assert [e["deleted_rows"] for e in dele["recent"]] == [8]                # 실패한 요청(99)은 안 셈


async def test_service_status(client, db_session):
    h, _ = await make_account(db_session, "admin@test.kr")
    st = (await overview(client, h))["status"]
    assert st["db_ok"] is True and st["admin_count"] == 1 and st["uptime_seconds"] >= 0
    assert st["db_revision"] is None            # 시험용 DB에는 마이그레이션 표가 없다
    assert st["server_started_at"]


async def test_no_personal_identifiers_in_response(client, db_session, seeded):
    h, uid = await make_account(db_session, "admin@test.kr")
    raw = await client.get("/v1/admin/overview", headers=h)
    text = raw.text
    assert "@" not in text and uid not in text and "u0" not in text
    d = raw.json()["data"]
    keys = {k for s in d["funnel"] for k in s} | {k for e in d["deletions"]["recent"] for k in e}
    assert not keys & {"user_id", "email", "deletion_request_id"}


async def test_csv_has_only_aggregates_and_is_recorded(client, db_session, seeded):
    h, uid = await make_account(db_session, "admin@test.kr")
    r = await client.get("/v1/admin/overview/export.csv", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"] and r.headers["cache-control"] == "no-store"
    assert r.content.startswith(b"\xef\xbb\xbf")                              # 엑셀용 BOM
    text = r.content.decode("utf-8-sig")
    assert "@" not in text and uid not in text and "u0" not in text          # 이메일·사용자 번호 없음
    rows = list(csv.reader(io.StringIO(text)))
    sections = {r[0] for r in rows if r}
    assert sections == {"meta", "funnel", "consent", "mission", "daily"}
    funnel = {r[1]: r[3] for r in rows if r and r[0] == "funnel" and r[1] != "code"}
    assert funnel["signup"] == "8" and funnel["challenge_completed"] == "1"
    assert sum(1 for r in rows if r and r[0] == "mission") == 1 + 10         # 머리줄 + 미션 10개
    await client.get("/v1/admin/overview/export.csv", headers=h)
    async with db_session() as s:
        actions = [a.action for a in (await s.execute(select(AdminAuditLog))).scalars()]
    assert actions.count("overview_csv_export") == 2                         # 내려받을 때마다 기록(중복 방지 없음)


async def test_view_is_recorded_once_per_window(client, db_session):
    h, _ = await make_account(db_session, "admin@test.kr")
    for _ in range(3):
        await overview(client, h)
    async with db_session() as s:
        actions = [a.action for a in (await s.execute(select(AdminAuditLog))).scalars()]
    assert actions.count("overview_view") == 1


# ---------------------------------------------------------------- 날짜별 활동 (한국 시각 기준)
KST = timezone(timedelta(hours=9))


def kst_noon(days_ago: int) -> datetime:
    """오늘(한국 시각)에서 days_ago일 전 정오를 UTC(시간대 표시 없음)로."""
    today = utcnow().replace(tzinfo=timezone.utc).astimezone(KST).date()
    day = today - timedelta(days=days_ago)
    return datetime(day.year, day.month, day.day, 12, tzinfo=KST).astimezone(timezone.utc).replace(tzinfo=None)


async def add_login(s, account: str, at: datetime) -> None:
    s.add(AccessLog(account_id=account, event="login", ip="203.0.113.7", created_at=at))


async def activity(client, h, days: int = 14) -> dict:
    r = await client.get(f"/v1/admin/overview?days={days}", headers=h)
    assert r.status_code == 200, r.text
    return {a["date"]: a for a in r.json()["data"]["activity"]}


async def test_daily_activity_counts(client, db_session):
    h, _ = await make_account(db_session, "admin@test.kr")
    async with db_session() as s:
        a, b, c = "acct-a", "acct-b", "acct-c"
        for who, ago in ((a, 3), (a, 1), (a, 0), (b, 1), (b, 1), (b, 0), (c, 0)):
            await add_login(s, who, kst_noon(ago))
        for ago in (3, 1, 0, 20):                       # 가입 (20일 전은 14일 창 밖)
            s.add(User(email=f"s{ago}@test.kr", password_hash="x", status="active", created_at=kst_noon(ago)))
        await s.commit()
    days = await activity(client, h, 14)
    ordered = list(days.values())
    assert len(ordered) == 14 and ordered[0]["date"] < ordered[-1]["date"]          # 빈 날도 0으로 채워 오래된 날부터
    today, d1, d3 = ordered[-1], ordered[-2], ordered[-4]
    assert (today["logins"], today["active_users"], today["returning_users"], today["signups"]) == (3, 3, 2, 2)   # 가입 2: 오늘 가입자 + 관리자
    assert (d1["logins"], d1["active_users"], d1["returning_users"], d1["signups"]) == (3, 2, 1, 1)
    assert (d3["logins"], d3["active_users"], d3["returning_users"], d3["signups"]) == (1, 1, 0, 1)
    assert sum(1 for d in ordered if d["logins"] == 0) == 11                         # 나머지 11일은 0
    assert sum(d["signups"] for d in ordered) == 4                                  # 20일 전 가입은 14일 창에 안 들어옴
    assert sum(d["signups"] for d in (await activity(client, h, 30)).values()) == 5   # 30일 창에는 들어옴


async def test_daily_activity_uses_korean_day_boundaries(client, db_session):
    h, _ = await make_account(db_session, "admin@test.kr")
    today_kst = utcnow().replace(tzinfo=timezone.utc).astimezone(KST).date()
    day = today_kst - timedelta(days=2)
    last_second = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=KST).astimezone(timezone.utc).replace(tzinfo=None)
    first_second = last_second + timedelta(seconds=1)                               # 한국 시각으로 다음 날 00:00:00
    async with db_session() as s:
        await add_login(s, "late", last_second)
        await add_login(s, "early", first_second)
        await s.commit()
    days = await activity(client, h, 14)
    assert days[day.isoformat()]["logins"] == 1 and days[(day + timedelta(days=1)).isoformat()]["logins"] == 1


async def test_daily_activity_has_only_counts(client, db_session):
    h, uid = await make_account(db_session, "admin@test.kr")
    async with db_session() as s:
        await add_login(s, "acct-secret-id", kst_noon(0))
        await s.commit()
    raw = await client.get("/v1/admin/overview", headers=h)
    assert "acct-secret-id" not in raw.text and "203.0.113.7" not in raw.text and uid not in raw.text   # 계정 번호·IP 없음
    keys = {k for a in raw.json()["data"]["activity"] for k in a}
    assert keys == {"date", "signups", "logins", "active_users", "returning_users"}


async def test_daily_activity_days_limits(client, db_session):
    h, _ = await make_account(db_session, "admin@test.kr")
    for bad in (0, 91, -1):
        assert (await client.get(f"/v1/admin/overview?days={bad}", headers=h)).status_code == 422
    assert len(await activity(client, h, 1)) == 1 and len(await activity(client, h, 90)) == 90


async def test_csv_has_daily_section_without_ids(client, db_session):
    h, _ = await make_account(db_session, "admin@test.kr")
    async with db_session() as s:
        await add_login(s, "acct-secret-id", kst_noon(0))
        await s.commit()
    r = await client.get("/v1/admin/overview/export.csv", headers=h)
    text = r.content.decode("utf-8-sig")
    rows = [row for row in csv.reader(io.StringIO(text)) if row and row[0] == "daily"]
    assert rows[0][1:] == ["date_kst", "signups", "logins", "active_users", "returning_users"] and len(rows) == 1 + 90
    assert "acct-secret-id" not in text and "203.0.113.7" not in text
