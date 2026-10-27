"""기간별 이탈 분석(/v1/admin/overview/journey): 실제 기록 기준 단계별 인원, 건너뛰고 온 사람, 챌린지 직접 기록일."""
from datetime import date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, update

from app.models.admin_audit import AdminAuditLog
from app.models.challenge import Challenge, ChallengeCycle, ChallengeLog, CycleChallenge
from app.models.eligibility import EligibilityAssessment
from app.models.health import HealthRecord
from app.models.prediction import PredictionJob
from app.models.survey import SurveyInstance, SurveyVersion
from app.models.user import User
from app.services import admin_overview_service, demo_autofill_service
from tests.conftest import make_program
from tests.test_admin_overview import make_account, wired  # noqa: F401 (wired는 자동 적용 픽스처)

pytestmark = pytest.mark.asyncio
NOW = datetime(2026, 10, 23, 3, 0)          # UTC (한국 10/23 12:00)
URL = "/v1/admin/overview/journey"


async def signed_up_at(Session, uid: str, kst: datetime) -> None:
    async with Session() as s:
        await s.execute(update(User).where(User.user_id == uid).values(created_at=kst - timedelta(hours=9)))
        await s.commit()


async def add_cycle(s, uid: str, challenge_ids: list[str], number: int, status: str, own_days: int = 0, filled_days: int = 0, program=None):
    if program is None:
        program = make_program(uid, now=NOW)
        s.add(program)
        await s.flush()
    cyc = ChallengeCycle(user_id=uid, program_id=program.program_id, cycle_number=number, started_on=date(2026, 10, 22),
                         ended_on=date(2026, 11, 18), status=status, created_at=NOW, updated_at=NOW)
    s.add(cyc)
    await s.flush()
    ccs = [CycleChallenge(cycle_id=cyc.cycle_id, challenge_id=cid, selection_type="fixed", difficulty="easy", weekly_target=7)
           for cid in challenge_ids]
    s.add_all(ccs)
    await s.flush()
    cc = ccs[0]
    for d in range(own_days):        # 본인이 직접 남긴 기록 (같은 날 미션 두 개를 기록해도 하루)
        for one in ccs:
            s.add(ChallengeLog(cycle_challenge_id=one.cycle_challenge_id, log_date=date(2026, 10, 22) + timedelta(days=d),
                               status="completed", recorded_at=NOW, updated_at=NOW))
    for d in range(filled_days):     # 체험 자동 채움 기록 (note 앞머리로 구분)
        s.add(ChallengeLog(cycle_challenge_id=cc.cycle_challenge_id, log_date=date(2026, 10, 25) + timedelta(days=d),
                           status="completed", note=f"{demo_autofill_service.MARK} steady", recorded_at=NOW, updated_at=NOW))
    return program


@pytest_asyncio.fixture
async def trial(db_session):
    """체험 기간(한국 10/22~10/25) 가입 7명 + 관리자 1명 + 기간 밖 1명."""
    admin_h, admin_id = await make_account(db_session, "admin@test.kr")
    _, early = await make_account(db_session, "early@test.kr")
    await signed_up_at(db_session, early, datetime(2026, 10, 20, 12))
    await signed_up_at(db_session, admin_id, datetime(2026, 10, 22, 9))
    ids = []
    for n in range(7):
        _, uid = await make_account(db_session, f"t{n}@test.kr")
        await signed_up_at(db_session, uid, datetime(2026, 10, 22, 10) + timedelta(hours=n))
        ids.append(uid)
    u0, u1, u2, u3, u4, u5, u6 = ids
    async with db_session() as s:
        challenge_ids = list((await s.execute(select(Challenge.challenge_id).limit(2))).scalars())
        assert len(challenge_ids) == 2
        for uid in [u1, u2, u3, u4, u5, u6]:
            s.add(EligibilityAssessment(user_id=uid, result_code="eligible", age_eligible=True, diagnosed_cad=False,
                                        emergency_flag=False, assessed_at=NOW))
        for uid in [u2, u3, u4, u5, u6]:
            s.add(HealthRecord(user_id=uid, health_schema_id="schema-1", input_type="initial", examination_date=date(2026, 10, 22), created_at=NOW))
        ver = SurveyVersion(survey_type="initial_lifestyle", version="j1", active_from=NOW)
        s.add(ver)
        await s.flush()
        for uid in [u3, u4, u6]:
            s.add(SurveyInstance(user_id=uid, survey_version_id=ver.survey_version_id, status="submitted", started_at=NOW, submitted_at=NOW))
        for n, uid in enumerate([u3, u4, u6]):
            s.add(PredictionJob(prediction_job_id=f"jj{n}", user_id=uid, health_record_id=f"hr{n}", request_type="initial", status="completed", requested_at=NOW))
        p4 = await add_cycle(s, u4, challenge_ids, 1, "completed", own_days=3, filled_days=20)
        await add_cycle(s, u4, challenge_ids, 2, "active", program=p4)
        await add_cycle(s, u5, challenge_ids, 1, "active", own_days=1, filled_days=25)     # 설문·분석 없이 시작
        await add_cycle(s, u6, challenge_ids, 1, "incomplete", own_days=2)
        await s.commit()
    return admin_h, ids


async def get(client, h, **params):
    r = await client.get(URL, headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def test_실제_기록으로_세고_건너뛴_사람과_넘어오지_않은_사람을_나눈다(client, db_session, trial):
    h, ids = trial
    d = await get(client, h, **{"from": "2026-10-22", "to": "2026-10-25"})
    assert d["cohort"] == 7 and d["admins_excluded"] == 1
    st = {s["code"]: s for s in d["stages"]}
    assert [s["users"] for s in d["stages"]] == [7, 6, 5, 3, 3, 3, 1]
    assert (st["survey"]["lost"], st["survey"]["skipped_previous"]) == (2, 0)          # 설문 없이 멈춘 u2, 설문 없이 챌린지로 간 u5
    assert (st["challenge_started"]["lost"], st["challenge_started"]["skipped_previous"]) == (1, 1)   # 분석 후 멈춘 u3, 분석 없이 온 u5
    assert [s["code"] for s in d["stages"] if s["biggest_loss"]] == ["survey"]
    assert d["challenge_without_prediction"] == [{"user_id_short": ids[5][-8:], "signed_up_kst": "10-22 15:00"}]


async def test_직접_기록일은_자동_채움을_빼고_날짜로_센다(client, db_session, trial):
    h, _ = trial
    d = await get(client, h, **{"from": "2026-10-22", "to": "2026-10-25"})
    days = {r["bucket"]: r for r in d["record_days"]}
    assert days["3일 이상"] == {"bucket": "3일 이상", "users": 1, "finished_4w": 1, "started_next": 1}
    assert days["2일"] == {"bucket": "2일", "users": 1, "finished_4w": 1, "started_next": 0}
    assert days["1일"] == {"bucket": "1일", "users": 1, "finished_4w": 0, "started_next": 0}   # 자동 채움 25일은 빼고 1일
    assert days["0일"]["users"] == 0


async def test_관리자를_포함하거나_기간을_비우면_그만큼_센다(client, db_session, trial):
    h, _ = trial
    assert (await get(client, h, **{"from": "2026-10-22", "to": "2026-10-25", "exclude_admins": "false"}))["cohort"] == 8
    assert (await get(client, h))["cohort"] == 8                         # 기간 없음: 기간 밖 1명 포함, 관리자 제외


async def test_기간이_거꾸로면_거부하고_관리자만_볼_수_있다(client, db_session, trial):
    h, _ = trial
    r = await client.get(URL, headers=h, params={"from": "2026-10-25", "to": "2026-10-22"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_PERIOD"
    user_h, _ = await make_account(db_session, "plain@test.kr")
    assert (await client.get(URL, headers=user_h)).status_code == 403


async def test_열람은_관리자_기록에_남고_응답에_개인정보가_없다(client, db_session, trial):
    h, _ = trial
    r = await client.get(URL, headers=h, params={"from": "2026-10-22", "to": "2026-10-25"})
    assert "@test.kr" not in r.text
    async with db_session() as s:
        logs = (await s.execute(select(AdminAuditLog).where(AdminAuditLog.action == "journey_view"))).scalars().all()
    assert len(logs) == 1 and "2026-10-22 ~ 2026-10-25" in logs[0].detail


def test_자동_채움_표시가_체험_자동_채움_코드와_같다():
    assert admin_overview_service.DEMO_MARK == demo_autofill_service.MARK
