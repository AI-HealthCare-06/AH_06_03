"""테스트용 DB(SQLite 메모리)와 API 클라이언트. MySQL 없이 돌아간다."""
import importlib.util
from datetime import date, datetime
from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (테이블 설계도 등록)
from app.core.db.databases import Base, async_get_db
from app.core.security import create_access_token
from app.main import app
from app.models.challenge import Challenge, ChallengeCategory, ChallengeLevel
from app.models.health import HealthInputSchema, HealthMeasurement, HealthRecord
from app.models.survey import SurveyInstance, SurveyOption, SurveyQuestion, SurveyResponse, SurveyVersion
from app.models.user import User, UserProfile

ROOT = Path(__file__).resolve().parent.parent


def _seed_module():
    """챌린지 시드는 마이그레이션 파일의 목록을 그대로 쓴다."""
    path = next((ROOT / "alembic" / "versions").glob("*_create_challenge_tables.py"))
    spec = importlib.util.spec_from_file_location("challenge_seed", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool,
                                 connect_args={"check_same_thread": False})
    # MySQL 전용 기본값 current_timestamp(0) → SQLite에서 쓸 수 있는 CURRENT_TIMESTAMP
    for table in Base.metadata.tables.values():
        for col in table.columns:
            d = col.server_default
            if d is not None and "current_timestamp(0)" in str(getattr(d, "arg", "")):
                col.server_default.arg = text("CURRENT_TIMESTAMP")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    seed = _seed_module()
    async with Session() as s:
        cat_ids = {}
        for n, (code, name, order) in enumerate(seed.CATEGORIES, start=1):
            cat_ids[code] = seed._cat_id(n)
            s.add(ChallengeCategory(category_id=cat_ids[code], category_code=code, category_name=name,
                                    display_order=order, active=True))
        await s.flush()
        for n, (code, cat, name, desc, role, diff, target, cfg) in enumerate(seed.MISSIONS, start=1):
            s.add(Challenge(challenge_id=seed._mission_id(n), category_id=cat_ids[cat], challenge_code=code,
                            challenge_name=name, description=desc, mission_role=role, proof_type="self_record",
                            active=True))
        await s.flush()
        for n, (_, _, _, _, _, diff, target, cfg) in enumerate(seed.MISSIONS, start=1):
            s.add(ChallengeLevel(challenge_level_id=seed._level_id(n), challenge_id=seed._mission_id(n),
                                 difficulty=diff, weekly_target=target, target_config=cfg))
        s.add(HealthInputSchema(health_schema_id="schema-1", schema_version="v1.9", model_scope="BOTH",
                                active_from=datetime(2026, 10, 1)))
        await s.commit()

    async def override():
        async with Session() as s:
            yield s

    app.dependency_overrides[async_get_db] = override
    yield Session
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def make_user(Session, *, sex="male", birth=date(1981, 3, 1), measurements: dict, answers: dict | None = None,
                    exam=date(2026, 10, 8)) -> dict:
    """회원 + 건강기록 + (선택) 설문 답안지를 만들고 인증 헤더를 돌려준다.
    measurements: {"SMOKING": "current", "HEIGHT": 175, ...}
    answers: {"N0": ("o30", 30), "P1": ("none", None), "P2": (None, 5000), ...}
    질문 코드 → (보기 코드, 점수). 보기 코드가 None이면 숫자 답(점수 자리에 값)"""
    now = datetime(2026, 10, 8, 9, 0)
    async with Session() as s:
        user = User(email=f"{id(measurements)}@test.kr", password_hash="x", status="active")
        s.add(user)
        await s.flush()
        s.add(UserProfile(user_id=user.user_id, sex=sex, birth_date=birth))
        rec = HealthRecord(user_id=user.user_id, health_schema_id="schema-1", input_type="initial",
                           examination_date=exam, created_at=now)
        s.add(rec)
        await s.flush()
        for code, v in measurements.items():
            num = isinstance(v, (int, float)) and not isinstance(v, bool)
            s.add(HealthMeasurement(health_record_id=rec.health_record_id, metric_code=code,
                                    value_num=v if num else None, value_code=None if num else str(v).lower(),
                                    measured_on=exam, created_at=now))
        if answers:
            ver = SurveyVersion(survey_type="initial_lifestyle", version=f"t{id(answers)}", active_from=now)
            s.add(ver)
            await s.flush()
            inst = SurveyInstance(user_id=user.user_id, survey_version_id=ver.survey_version_id,
                                  status="submitted", started_at=now, submitted_at=now)
            s.add(inst)
            await s.flush()
            for i, (q_code, (o_code, score)) in enumerate(answers.items(), start=1):
                q = SurveyQuestion(survey_version_id=ver.survey_version_id, question_code=q_code,
                                   question_text=q_code, display_order=i, required=False,
                                   answer_type="number" if o_code is None else "single_select")
                s.add(q)
                await s.flush()
                if o_code is None:  # 숫자 답 (P2 걸음 수): 보기 없이 value_num
                    s.add(SurveyResponse(survey_instance_id=inst.survey_instance_id, question_id=q.question_id,
                                         value_num=score, created_at=now))
                    continue
                o = SurveyOption(question_id=q.question_id, option_code=o_code, option_text=o_code,
                                 numeric_score=score, display_order=1)
                s.add(o)
                await s.flush()
                s.add(SurveyResponse(survey_instance_id=inst.survey_instance_id, question_id=q.question_id,
                                     option_id=o.option_id, created_at=now))
        await s.commit()
        return {"Authorization": f"Bearer {create_access_token(user.user_id)}"}
