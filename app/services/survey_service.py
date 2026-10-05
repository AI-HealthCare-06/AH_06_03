"""설문 매니저. 판단과 조립을 한다."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.repositories import health_repository, survey_repository
from app.schemas.survey import OptionResult, QuestionResult, SurveyResult, SurveyInstanceResult


async def get_active_survey(db: AsyncSession, survey_type: str) -> SurveyResult:
    version = await survey_repository.get_active_version(db, survey_type)
    if version is None:
        raise AppError(404, "SURVEY_NOT_FOUND", "진행 중인 설문이 없습니다.")

    questions = await survey_repository.get_questions(db, version.survey_version_id)
    options = await survey_repository.get_options(db, [q.question_id for q in questions])

    # 🧺 보기를 질문별 바구니에 나눠 담기
    baskets = {}
    for o in options:
        baskets.setdefault(o.question_id, []).append(
            OptionResult(option_id=o.option_id, option_code=o.option_code, option_text=o.option_text)
        )

    return SurveyResult(
        survey_version_id=version.survey_version_id,
        survey_type=version.survey_type,
        version=version.version,
        questions=[
            QuestionResult(
                question_id=q.question_id,
                question_code=q.question_code,
                question_text=q.question_text,
                required=q.required,
                options=baskets.get(q.question_id, []),
            )
            for q in questions
        ],
    )

async def start_survey(
    db: AsyncSession, user_id: str, survey_version_id: str, health_record_id: str | None
) -> SurveyInstanceResult:
    """2번 창구: 답안지 받기."""
    # 1. 지금 쓰는 설문지가 맞는지
    version = await survey_repository.get_version(db, survey_version_id)
    if version is None or version.active_to is not None:
        raise AppError(404, "SURVEY_NOT_FOUND", "진행 중인 설문이 없습니다.")
 
    # 2. 검진 번호를 보냈다면, 내 검진이 맞는지
    if health_record_id is not None:
        record = await health_repository.get_health_record(db, health_record_id)
        if record is None or record.user_id != user_id:
            raise AppError(404, "HEALTH_RECORD_NOT_FOUND", "건강기록을 찾을 수 없습니다.")
 
    # 3. 빈 답안지 만들기
    instance = await survey_repository.create_instance(db, user_id, survey_version_id, health_record_id, utcnow())
    await db.commit()
    return SurveyInstanceResult(
        survey_instance_id=instance.survey_instance_id,
        survey_version_id=instance.survey_version_id,
        status=instance.status,
    )

async def save_responses(
    db: AsyncSession, user_id: str, survey_instance_id: str, items: list[dict]
) -> SurveyInstanceResult:
    """3번 창구: 답 적기. 같은 질문에 다시 답하면 새 답으로 바꾼다."""
    # 1. 내 답안지인가?
    instance = await survey_repository.get_instance(db, survey_instance_id)
    if instance is None or instance.user_id != user_id:
        raise AppError(404, "SURVEY_INSTANCE_NOT_FOUND", "설문 답안지를 찾을 수 없습니다.")

    # 2. 아직 제출 전인가?
    if instance.status != "started":
        raise AppError(409, "SURVEY_ALREADY_SUBMITTED", "이미 제출한 설문입니다.")

    # 3. 질문·보기가 맞게 짝지어졌나? (허락 목록 만들기)
    questions = await survey_repository.get_questions(db, instance.survey_version_id)
    options = await survey_repository.get_options(db, [q.question_id for q in questions])
    allowed = {q.question_id: set() for q in questions}
    for o in options:
        allowed[o.question_id].add(o.option_id)

    for item in items:
        if item["question_id"] not in allowed:
            raise AppError(422, "SURVEY_QUESTION_INVALID", "이 설문에 없는 질문입니다.")
        if item["option_id"] not in allowed[item["question_id"]]:
            raise AppError(422, "SURVEY_OPTION_INVALID", "이 질문에 없는 보기입니다.")

    question_ids = [item["question_id"] for item in items]
    if len(set(question_ids)) != len(question_ids):
        raise AppError(422, "SURVEY_QUESTION_DUPLICATED", "한 질문에 답을 두 번 보냈습니다.")

    # 4. 예전 답 지우기 → 새 답 넣기 → 진짜 저장
    await survey_repository.delete_responses(db, survey_instance_id, question_ids)
    await survey_repository.add_responses(db, survey_instance_id, items, utcnow())
    await db.commit()
    return SurveyInstanceResult(
        survey_instance_id=instance.survey_instance_id,
        survey_version_id=instance.survey_version_id,
        status=instance.status,
    )

async def submit_survey(db: AsyncSession, user_id: str, survey_instance_id: str) -> SurveyInstanceResult:
    """4번 창구: 답안지 내기."""
    instance = await survey_repository.get_instance(db, survey_instance_id)
    if instance is None or instance.user_id != user_id:
        raise AppError(404, "SURVEY_INSTANCE_NOT_FOUND", "설문 답안지를 찾을 수 없습니다.")
    if instance.status != "started":
        raise AppError(409, "SURVEY_ALREADY_SUBMITTED", "이미 제출한 설문입니다.")

    # 필수 질문에 다 답했나?
    questions = await survey_repository.get_questions(db, instance.survey_version_id)
    answered = await survey_repository.get_answered_question_ids(db, survey_instance_id)
    missing = [q.question_code for q in questions if q.required and q.question_id not in answered]
    if missing:
        raise AppError(422, "SURVEY_INCOMPLETE", f"답하지 않은 필수 질문이 있습니다: {', '.join(missing)}")

    # 답안지 내기
    instance.status = "submitted"
    instance.submitted_at = utcnow()
    await db.commit()
    return SurveyInstanceResult(
        survey_instance_id=instance.survey_instance_id,
        survey_version_id=instance.survey_version_id,
        status=instance.status,
    )