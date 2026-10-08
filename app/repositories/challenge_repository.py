"""챌린지 창고 담당. DB에 넣고 꺼내는 일만 한다. 저장 확정(commit)은 서비스가 한다."""
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import (
    Challenge, ChallengeCategory, ChallengeCycle, ChallengeLevel, ChallengeLog, CycleChallenge, UserClassification,
)
from app.models.health import HealthMeasurement, HealthRecord
from app.models.prediction import Prediction, PredictionJob
from app.models.survey import SurveyOption, SurveyQuestion, SurveyResponse


async def get_catalog(db: AsyncSession) -> list[tuple[Challenge, ChallengeCategory, ChallengeLevel]]:
    """미션 + 카테고리 + 난이도 행 (미션당 1행)."""
    result = await db.execute(
        select(Challenge, ChallengeCategory, ChallengeLevel)
        .join(ChallengeCategory, ChallengeCategory.category_id == Challenge.category_id)
        .join(ChallengeLevel, ChallengeLevel.challenge_id == Challenge.challenge_id)
        .order_by(ChallengeCategory.display_order, Challenge.challenge_code)
    )
    return list(result.tuples().all())


async def get_latest_health_record(db: AsyncSession, user_id: str) -> HealthRecord | None:
    """판정 기준 건강기록: 최초 입력·재평가 중 가장 최근 (주간 혈압 기록은 제외)."""
    result = await db.execute(
        select(HealthRecord)
        .where(HealthRecord.user_id == user_id)
        .where(HealthRecord.input_type.in_(["initial", "interim_reassessment", "full_reassessment"]))
        .order_by(HealthRecord.examination_date.desc(), HealthRecord.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_measurement_map(db: AsyncSession, health_record_id: str) -> dict[str, HealthMeasurement]:
    result = await db.execute(
        select(HealthMeasurement).where(HealthMeasurement.health_record_id == health_record_id)
    )
    return {m.metric_code: m for m in result.scalars().all()}


async def get_survey_answers(db: AsyncSession, survey_instance_id: str) -> dict[str, tuple[str, float | None]]:
    """답안지의 답을 {질문 코드: (보기 코드, 점수)}로 꺼낸다."""
    result = await db.execute(
        select(SurveyQuestion.question_code, SurveyOption.option_code, SurveyOption.numeric_score)
        .select_from(SurveyResponse)
        .join(SurveyQuestion, SurveyQuestion.question_id == SurveyResponse.question_id)
        .join(SurveyOption, SurveyOption.option_id == SurveyResponse.option_id)
        .where(SurveyResponse.survey_instance_id == survey_instance_id)
    )
    return {q: (o, s) for q, o, s in result.all()}


async def get_active_cycle(db: AsyncSession, user_id: str) -> ChallengeCycle | None:
    result = await db.execute(
        select(ChallengeCycle)
        .where(ChallengeCycle.user_id == user_id)
        .where(ChallengeCycle.status == "active")
        .order_by(ChallengeCycle.started_on.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_cycle(db: AsyncSession, cycle_id: str) -> ChallengeCycle | None:
    return await db.get(ChallengeCycle, cycle_id)


async def get_cycles(db: AsyncSession, user_id: str) -> list[ChallengeCycle]:
    """내 사이클 전부 (최근 시작부터)."""
    result = await db.execute(
        select(ChallengeCycle)
        .where(ChallengeCycle.user_id == user_id)
        .order_by(ChallengeCycle.started_on.desc(), ChallengeCycle.created_at.desc())
    )
    return list(result.scalars().all())


async def get_cycle_missions(db: AsyncSession, cycle_id: str) -> list[tuple[CycleChallenge, Challenge]]:
    result = await db.execute(
        select(CycleChallenge, Challenge)
        .join(Challenge, Challenge.challenge_id == CycleChallenge.challenge_id)
        .where(CycleChallenge.cycle_id == cycle_id)
    )
    return list(result.tuples().all())


async def get_completed_codes(db: AsyncSession, user_id: str) -> set[str]:
    """이전 사이클에서 완료한 미션 코드 (REQ-CHAL-002)."""
    result = await db.execute(
        select(Challenge.challenge_code)
        .select_from(CycleChallenge)
        .join(ChallengeCycle, ChallengeCycle.cycle_id == CycleChallenge.cycle_id)
        .join(Challenge, Challenge.challenge_id == CycleChallenge.challenge_id)
        .where(ChallengeCycle.user_id == user_id)
        .where(CycleChallenge.status == "completed")
    )
    return set(result.scalars().all())


async def get_logs(db: AsyncSession, cycle_challenge_ids: list[str]) -> list[ChallengeLog]:
    if not cycle_challenge_ids:
        return []
    result = await db.execute(
        select(ChallengeLog)
        .where(ChallengeLog.cycle_challenge_id.in_(cycle_challenge_ids))
        .order_by(ChallengeLog.log_date)
    )
    return list(result.scalars().all())


async def get_log(db: AsyncSession, cycle_challenge_id: str, log_date: date) -> ChallengeLog | None:
    result = await db.execute(
        select(ChallengeLog)
        .where(ChallengeLog.cycle_challenge_id == cycle_challenge_id)
        .where(ChallengeLog.log_date == log_date)
    )
    return result.scalar_one_or_none()


async def create_cycle(
    db: AsyncSession, user_id: str, cycle_number: int, started_on: date, ended_on: date, now: datetime
) -> ChallengeCycle:
    cycle = ChallengeCycle(
        user_id=user_id, cycle_number=cycle_number, started_on=started_on, ended_on=ended_on,
        status="active", created_at=now, updated_at=now,
    )
    db.add(cycle)
    await db.flush()
    return cycle


def add_cycle_mission(db: AsyncSession, cycle_id: str, challenge_id: str, selection_type: str,
                      difficulty: str, weekly_target: int, target_config: dict | None) -> CycleChallenge:
    cc = CycleChallenge(
        cycle_id=cycle_id, challenge_id=challenge_id, selection_type=selection_type,
        difficulty=difficulty, weekly_target=weekly_target, target_config=target_config, status="active",
    )
    db.add(cc)
    return cc


def add_classifications(db: AsyncSession, user_id: str, cycle_id: str, health_record_id: str | None,
                        survey_instance_id: str | None, values: dict, now: datetime) -> None:
    """건강정보 기반 분류는 health_record_id, 설문 기반 분류는 survey_instance_id를 같이 남긴다."""
    from_health = {"smoker", "drinker", "bp_160_100", "overweight"}
    for code, value in values.items():
        db.add(UserClassification(
            user_id=user_id, cycle_id=cycle_id,
            health_record_id=health_record_id if code in from_health else None,
            survey_instance_id=None if code in from_health else survey_instance_id,
            classification_code=code,
            classification_value=value if isinstance(value, dict) else {"value": value},
            classified_at=now,
        ))


def add_log(db: AsyncSession, cycle_challenge_id: str, log_date: date, values: dict, now: datetime) -> ChallengeLog:
    log = ChallengeLog(cycle_challenge_id=cycle_challenge_id, log_date=log_date, recorded_at=now, updated_at=now,
                       **values)
    db.add(log)
    return log


# ---------------------------------------------------------------- 4주 재입력 (가이드 §6)
async def get_basis_record(db: AsyncSession, user_id: str, on_or_before: date, exclude_cycle_id: str) -> HealthRecord | None:
    """사이클을 시작할 때 기준이 된 건강기록: 시작일까지의 최초 입력·재평가 중 가장 최근."""
    result = await db.execute(
        select(HealthRecord)
        .where(HealthRecord.user_id == user_id)
        .where(HealthRecord.input_type.in_(["initial", "interim_reassessment", "full_reassessment"]))
        .where(HealthRecord.examination_date <= on_or_before)
        .where((HealthRecord.cycle_id.is_(None)) | (HealthRecord.cycle_id != exclude_cycle_id))
        .order_by(HealthRecord.examination_date.desc(), HealthRecord.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_reassessment(db: AsyncSession, cycle_id: str) -> HealthRecord | None:
    result = await db.execute(
        select(HealthRecord)
        .where(HealthRecord.cycle_id == cycle_id)
        .where(HealthRecord.input_type == "interim_reassessment")
        .order_by(HealthRecord.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_reassessed_cycle_ids(db: AsyncSession, cycle_ids: list[str]) -> set[str]:
    if not cycle_ids:
        return set()
    result = await db.execute(
        select(HealthRecord.cycle_id)
        .where(HealthRecord.cycle_id.in_(cycle_ids))
        .where(HealthRecord.input_type == "interim_reassessment")
    )
    return set(result.scalars().all())


async def get_latest_job_predictions(db: AsyncSession, health_record_id: str) -> list[Prediction]:
    """그 건강기록으로 돌린 가장 최근 완료 예측의 모델별 결과."""
    job = (await db.execute(
        select(PredictionJob)
        .where(PredictionJob.health_record_id == health_record_id)
        .where(PredictionJob.status == "completed")
        .order_by(PredictionJob.completed_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if job is None:
        return []
    result = await db.execute(select(Prediction).where(Prediction.prediction_job_id == job.prediction_job_id))
    return list(result.scalars().all())
