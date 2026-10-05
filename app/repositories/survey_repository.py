"""설문 창고 담당. DB에 넣고 꺼내는 일만 한다."""
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime


from app.models.survey import SurveyOption, SurveyQuestion, SurveyVersion, SurveyInstance, SurveyResponse



async def get_active_version(db: AsyncSession, survey_type: str) -> SurveyVersion | None:
    """📚 지금 쓰는 설문지 (끝나는 날이 비어 있는 것 중 가장 최근)."""
    result = await db.execute(
        select(SurveyVersion)
        .where(SurveyVersion.survey_type == survey_type)
        .where(SurveyVersion.active_to.is_(None))
        .order_by(SurveyVersion.active_from.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_questions(db: AsyncSession, survey_version_id: str) -> list[SurveyQuestion]:
    """❓ 그 설문지의 질문들 (화면 순서대로)."""
    result = await db.execute(
        select(SurveyQuestion)
        .where(SurveyQuestion.survey_version_id == survey_version_id)
        .order_by(SurveyQuestion.display_order)
    )
    return list(result.scalars().all())

async def get_options(db: AsyncSession, question_ids: list[str]) -> list[SurveyOption]:
    """🔘 그 질문들의 보기를 한 번에 (화면 순서대로)."""
    if not question_ids:
        return []
    result = await db.execute(
        select(SurveyOption)
        .where(SurveyOption.question_id.in_(question_ids))
        .order_by(SurveyOption.display_order)
    )
    return list(result.scalars().all())

async def get_version(db: AsyncSession, survey_version_id: str) -> SurveyVersion | None:
    """📚 설문지 번호로 설문지를 찾는다."""
    return await db.get(SurveyVersion, survey_version_id)


async def create_instance(
    db: AsyncSession, user_id: str, survey_version_id: str, health_record_id: str | None, now: datetime
) -> SurveyInstance:
    """📋 빈 답안지를 만든다. 저장 확정(commit)은 서비스가 한다."""
    instance = SurveyInstance(
        user_id=user_id,
        survey_version_id=survey_version_id,
        health_record_id=health_record_id,
        started_at=now,
    )
    db.add(instance)
    await db.flush()
    return instance

async def get_instance(db: AsyncSession, survey_instance_id: str) -> SurveyInstance | None:
    """📋 답안지 번호로 답안지를 찾는다."""
    return await db.get(SurveyInstance, survey_instance_id)


async def delete_responses(db: AsyncSession, survey_instance_id: str, question_ids: list[str]) -> None:
    """✔️ 이 답안지에서, 이 질문들의 예전 답을 지운다 (답 바꾸기용)."""
    await db.execute(
        delete(SurveyResponse)
        .where(SurveyResponse.survey_instance_id == survey_instance_id)
        .where(SurveyResponse.question_id.in_(question_ids))
    )


async def add_responses(
    db: AsyncSession, survey_instance_id: str, items: list[dict], now: datetime
) -> None:
    """✔️ 새 답들을 넣는다. 저장 확정(commit)은 서비스가 한다."""
    for item in items:
        db.add(SurveyResponse(
            survey_instance_id=survey_instance_id,
            question_id=item["question_id"],
            option_id=item["option_id"],
            created_at=now,
        ))

async def get_answered_question_ids(db: AsyncSession, survey_instance_id: str) -> set[str]:
    """✔️ 이 답안지에서 이미 답한 질문 번호들."""
    result = await db.execute(
        select(SurveyResponse.question_id)
        .where(SurveyResponse.survey_instance_id == survey_instance_id)
    )
    return set(result.scalars().all())

async def get_answers_for_model(db: AsyncSession, survey_instance_id: str) -> dict[str, str]:
    """✔️ 답안지의 답을 {질문 이름: 고른 보기의 모델 값}으로 꺼낸다."""
    result = await db.execute(
        select(SurveyQuestion.question_code, SurveyOption.model_value_code)
        .select_from(SurveyResponse)
        .join(SurveyQuestion, SurveyQuestion.question_id == SurveyResponse.question_id)
        .join(SurveyOption, SurveyOption.option_id == SurveyResponse.option_id)
        .where(SurveyResponse.survey_instance_id == survey_instance_id)
    )
    return {q_code: model_value for q_code, model_value in result.all()}


async def get_latest_submitted(db: AsyncSession, user_id: str) -> SurveyInstance | None:
    """📋 이 사람이 가장 최근에 제출한 답안지."""
    result = await db.execute(
        select(SurveyInstance)
        .where(SurveyInstance.user_id == user_id)
        .where(SurveyInstance.status == "submitted")
        .order_by(SurveyInstance.submitted_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()