"""챌린지 매니저. 건강정보·설문을 꺼내 판정하고, 사이클·매일 기록을 저장한다.

규칙은 app/services/challenge_rules.py, 문구는 app/services/challenge_catalog.py.
"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.challenge import ChallengeCycle
from app.repositories import challenge_repository, health_repository, prediction_repository, survey_repository, user_repository
from app.core.config import settings
from app.schemas.challenge import (
    AnswerOption, CycleMission, CycleResult, CycleSummary, DemoInfo, DemoStatus, ExcludedItem, FixedSlot, LogResult, MissionCard,
    MissionResult, ModelChange, ProgramCheckpoint, ProgramCycleRate, ProgramReviewResult, ProgramStatus, RecommendationResult,
    ReviewResult, Snapshot, SodiumResult, SurveyNeeded, WeekProgress,
)

from app.services import challenge_reward_service, challenge_rules as rules
from app.services import demo_autofill_service
from app.services import health_service, prediction_job_service
from app.services.challenge_catalog import (
    CATEGORY_NAMES, CYCLE_DAYS, CYCLE_WEEKS, KEEP_GOING_MESSAGE, MISSION_COMPLETE_RATE, MISSIONS, PROGRAM_CYCLES,
    SELECTABLE_NOTICE,
)
from app.services.model_input import age_on
from app.ml.predictor import similarity_level_b
from app.ml import predictor

ALC_WARNING = "오늘은 권장량을 넘었어요. 건강을 위해서는 술을 마시지 않는 것이 가장 좋아요."


def today_kst() -> date:
    """사용자 기준 날짜 (한국 시간)."""
    return (utcnow() + timedelta(hours=9)).date()


# ---------------------------------------------------------------- 카드
def _card(code: str, sex: str, ecig: str | None = None, completed_before: bool = False) -> MissionCard:
    m = MISSIONS[code]
    answers = m["answers"]
    if code == "ALC-1":
        answers = [("0", "안 마심"), ("1", "1잔"), ("2", "2잔"), ("3", "3잔 이상")] if sex == "male" \
            else [("0", "안 마심"), ("1", "1잔"), ("2", "2잔 이상")]
    notice = m["notice"]
    if code == "SMK-1" and ecig in ("daily", "occasional"):
        notice = f"{notice}. 전자담배도 함께 끊어요"
    return MissionCard(
        code=code, category=m["category"], category_name=CATEGORY_NAMES[m["category"]], name=m["name"],
        difficulty=m["difficulty"], weekly_target=m["weekly_target"], description=m["description"],
        evidence=m["evidence"], source=m["source"], notice=notice, question=m["question"],
        answers=[AnswerOption(code=c, label=l) for c, l in answers], completed_before=completed_before,
    )


# ---------------------------------------------------------------- 판정 재료
async def _load_facts(db: AsyncSession, user_id: str):
    """최근 건강기록 + 최근 제출 설문 → UserFacts."""
    profile = await user_repository.get_profile(db, user_id)
    if profile is None or profile.sex is None:
        raise AppError(422, "PREDICTION_SEX_REQUIRED", "성별을 먼저 입력해 주세요.")
    record = await challenge_repository.get_latest_health_record(db, user_id)
    if record is None:
        raise AppError(409, "HEALTH_RECORD_REQUIRED", "건강정보를 먼저 입력해 주세요.")

    m = await challenge_repository.get_measurement_map(db, record.health_record_id)

    def num(code):
        return m[code].value_num if code in m else None

    def code_(code):
        return m[code].value_code if code in m else None

    instance = await survey_repository.get_latest_submitted(db, user_id)
    raw = await challenge_repository.get_survey_answers(db, instance.survey_instance_id) if instance else {}
    answers = {q: o for q, (o, _, _) in raw.items() if o is not None}
    scores = {q: s for q, (_, s, _) in raw.items() if q in rules.NA_QUESTIONS and s is not None}
    steps = raw.get("P2", (None, None, None))[2]

    diabetes = code_("DIABETES")
    facts = rules.UserFacts(
        age=age_on(profile.birth_date, record.examination_date), sex=profile.sex,
        smoking=code_("SMOKING"), ecig=code_("ECIG"),
        drink_freq=code_("ALCOHOL_FREQ"), drink_amount=code_("ALCOHOL_AMOUNT"),
        sbp=num("SBP"), dbp=num("DBP"), height_cm=num("HEIGHT"), weight_kg=num("WEIGHT"),
        htn_status=code_("HTN_STATUS"), diabetes=None if diabetes is None else diabetes == "true",
        answers=answers, scores=scores,
        baseline_steps=int(steps) if steps is not None else None,  # P2 걸음 수 (숫자 답, "모르겠어요"면 없음)
    )
    return facts, record, instance


async def _active_codes(db: AsyncSession) -> tuple[set[str], dict, dict[str, int]]:
    """관리자가 노출 중인 미션 코드, 미션별 (Challenge, Level), 미션별 카테고리 순서."""
    rows = await challenge_repository.get_catalog(db)
    active = {ch.challenge_code for ch, cat, _ in rows if ch.active and cat.active}
    order = {ch.challenge_code: cat.display_order for ch, cat, _ in rows}
    return active, {ch.challenge_code: (ch, lv) for ch, _, lv in rows}, order


async def _next_cycle_number(db: AsyncSession, program_id: str) -> int:
    """프로그램 안에서 다음 사이클 번호를 계산한다: 1 → 2 → 3."""
    cycles = await challenge_repository.get_program_cycles(db, program_id)
    finished = sum(1 for cycle in cycles if cycle.status in ("completed", "incomplete"))
    return finished + 1


async def _get_or_create_current_program(db: AsyncSession, user_id: str):
    """첫 사이클을 시작할 때 프로그램 1을 만든다. 이미 있으면 그대로 사용한다."""
    program = await challenge_repository.get_latest_program(db, user_id)
    if program is not None:
        return program

    info = predictor.current_program_model_info()
    return await challenge_repository.create_program(
        db=db,
        user_id=user_id,
        program_number=1,
        model_a_version=info["model_a_version"],
        model_b_version=info["model_b_version"],
        model_updated_on=info["model_updated_on"],
        change_note=info["change_note"],
        now=utcnow(),
    )


async def _build_recommendation(db: AsyncSession, user_id: str):
    facts, record, instance = await _load_facts(db, user_id)
    c = rules.classify(facts)
    completed = await challenge_repository.get_completed_codes(db, user_id)
    rec = rules.recommend(c, facts.answers, completed)
    active, _, order = await _active_codes(db)
    # 노출 중인 것만, 관리자가 정한 카테고리 순서로 (같은 카테고리 안의 순서는 규칙 그대로)
    rec.candidates = sorted((code for code in rec.candidates if code in active), key=lambda code: order.get(code, 999))
    return facts, record, instance, c, rec


# ---------------------------------------------------------------- W09 추천
async def get_recommendation(db: AsyncSession, user_id: str) -> RecommendationResult:
    facts, _, _, c, rec = await _build_recommendation(db, user_id)
    sodium = c.get("sodium")
    done = set(rec.completed)

    program = await challenge_repository.get_latest_program(db, user_id)
    next_cycle_number = (
        await _next_cycle_number(db, program.program_id)
        if program is not None
        else 1
    )

    return RecommendationResult(
        cycle_number=next_cycle_number,
        total_cycles=PROGRAM_CYCLES,
        fixed=[
            FixedSlot(slot=s["slot"], slot_label=s["from"], selection_type=s["selection_type"],
                      mission=_card(s["code"], facts.sex, facts.ecig, s["code"] in done) if s["code"] else None)
            for s in rec.fixed
        ],
        candidates=[_card(code, facts.sex, completed_before=code in done) for code in rec.candidates],
        keep_going_message=KEEP_GOING_MESSAGE if done else None,
        excluded=[
            ExcludedItem(
                code=e.get("code"),
                kind=e["kind"],
                category=e.get("category") or MISSIONS[e["code"]]["category"],
                name=MISSIONS[e["code"]]["name"] if e.get("code") else f"{CATEGORY_NAMES[e['category']]} 미션",
                reason=e["reason"],
            )
            for e in rec.excluded
        ],
        survey_needed=[SurveyNeeded(category=cat, category_name=CATEGORY_NAMES[cat]) for cat in rec.survey_needed],
        all_good=rec.all_good,
        selectable_notice=SELECTABLE_NOTICE,
        sodium=SodiumResult(**sodium) if sodium else None,
    )


# ---------------------------------------------------------------- 사이클 종료 판정
async def _finalize_if_ended(db: AsyncSession, cycle: ChallengeCycle, today: date) -> None:
    """종료일이 지난 진행 중 사이클을 닫는다. 미션별 4주 달성률이 기준 이상이면 completed.
    사이클은 미션이 모두 completed면 completed, 아니면 incomplete (REQ-CHAL-007 목표 미달)."""
    if cycle.status != "active" or today <= cycle.ended_on:
        return
    await finalize_cycle(db, cycle)


async def finalize_cycle(db: AsyncSession, cycle: ChallengeCycle) -> None:
    """진행 중 사이클을 지금 닫는다(달성률 계산은 위와 같다). 체험용 자동 채움도 쓴다."""
    missions = await challenge_repository.get_cycle_missions(db, cycle.cycle_id)
    logs = await challenge_repository.get_logs(db, [cc.cycle_challenge_id for cc, _ in missions])
    all_done = True
    for cc, _ in missions:
        mine = [(l.log_date, l.status) for l in logs if l.cycle_challenge_id == cc.cycle_challenge_id]
        rate = rules.progress(cycle.started_on, cc.weekly_target, mine)["cycle_rate"]
        cc.status = "completed" if rate >= MISSION_COMPLETE_RATE else "incomplete"
        all_done = all_done and cc.status == "completed"

    cycle.status = "completed" if all_done else "incomplete"
    cycle.updated_at = utcnow()
    if cycle.status == "completed":
        await challenge_reward_service.reward_cycle_complete(db, cycle.user_id, cycle.cycle_id)   # 4주 완주 +50
    await db.commit()


async def _current_active(db: AsyncSession, user_id: str) -> ChallengeCycle | None:
    cycle = await challenge_repository.get_active_cycle(db, user_id)
    if cycle is not None:
        await _finalize_if_ended(db, cycle, today_kst())
        if cycle.status != "active":
            return None
    return cycle


# ---------------------------------------------------------------- 사이클 시작
async def start_cycle(db: AsyncSession, user_id: str, selected_code: str) -> CycleResult:
    if await _current_active(db, user_id) is not None:
        raise AppError(409, "CHALLENGE_CYCLE_ACTIVE", "진행 중인 챌린지가 있습니다.")
    # 현재 프로그램이 이미 3사이클을 끝냈다면 restart 전에는 새 사이클을 막는다.
    program = await challenge_repository.get_latest_program(db, user_id)
    if program is not None and await _next_cycle_number(db, program.program_id) > PROGRAM_CYCLES:
        raise AppError(
            409,
            "CHALLENGE_PROGRAM_COMPLETE",
            f"{PROGRAM_CYCLES * 4}주 챌린지를 모두 마쳤습니다. 새 12주를 시작해 주세요.",
        )

    facts, record, instance, c, rec = await _build_recommendation(db, user_id)
    # 분석(예측)을 마친 사람만 시작한다. 화면 순서를 건너뛰어도(주소로 바로 들어와도) 분석 결과 없이 챌린지가 돌지 않게 서버에서 막는다.
    if await prediction_repository.get_latest_completed_job(db, user_id) is None:
        raise AppError(409, "ANALYSIS_REQUIRED", "분석을 먼저 마쳐야 챌린지를 시작할 수 있어요.")
    if selected_code not in rec.candidates:
        raise AppError(422, "CHALLENGE_SELECTION_INVALID", "선택할 수 없는 미션입니다.")

        # 첫 사이클이라면 프로그램 1을 지금 만든다.
    if program is None:
        program = await _get_or_create_current_program(db, user_id)

    cycle_number = await _next_cycle_number(db, program.program_id)

    _, catalog, _ = await _active_codes(db)
    chosen = [(s["code"], s["selection_type"]) for s in rec.fixed if s["code"]] + [(selected_code, "selected")]

    now, today = utcnow(), today_kst()
    cycle = await challenge_repository.create_cycle(
        db,
        user_id,
        program.program_id,
        cycle_number,
        today,
        today + timedelta(days=CYCLE_DAYS - 1),
        now,
    )
    for code, selection in chosen:
        ch, lv = catalog[code]
        cfg = dict(lv.target_config or {})
        if code == "ACT-1":
            cfg["steps_target"] = (facts.baseline_steps or 0) + 2000
        challenge_repository.add_cycle_mission(
            db, cycle.cycle_id, ch.challenge_id, selection, lv.difficulty, lv.weekly_target, cfg or None
        )
    challenge_repository.add_classifications(
        db, user_id, cycle.cycle_id, record.health_record_id,
        instance.survey_instance_id if instance else None, c, now,
    )
    await db.commit()
    return await _cycle_result(db, cycle, facts.sex, today)


# ---------------------------------------------------------------- 조회
def _log_result(log) -> LogResult:
    return LogResult(
        log_date=log.log_date, status=log.status, answer=log.answer, quantity=log.quantity,
        limit_exceeded=log.limit_exceeded, warning=ALC_WARNING if log.limit_exceeded else None,
    )


async def _cycle_result(db: AsyncSession, cycle: ChallengeCycle, sex: str, today: date) -> CycleResult:
    missions = await challenge_repository.get_cycle_missions(db, cycle.cycle_id)
    logs = await challenge_repository.get_logs(db, [cc.cycle_challenge_id for cc, _ in missions])
    day = min(max((today - cycle.started_on).days + 1, 1), CYCLE_DAYS)

    items = []
    for cc, ch in missions:
        mine = [l for l in logs if l.cycle_challenge_id == cc.cycle_challenge_id]
        pairs = [(l.log_date, l.status) for l in mine]
        p = rules.progress(cycle.started_on, cc.weekly_target, pairs)
        today_log = next((l for l in mine if l.log_date == today), None)
        items.append(CycleMission(
            cycle_challenge_id=cc.cycle_challenge_id, selection_type=cc.selection_type, status=cc.status,
            card=_card(ch.challenge_code, sex), weekly_target=cc.weekly_target, target_config=cc.target_config,
            weeks=[WeekProgress(**w) for w in p["weeks"]], cycle_rate=p["cycle_rate"],
            streak=rules.streak(pairs, min(today, cycle.ended_on)),
            today_log=_log_result(today_log) if today_log else None,
            logs=[_log_result(l) for l in mine],
        ))
    order = {"fixed": 0, "replacement": 0, "selected": 1}
    items.sort(key=lambda i: order[i.selection_type])

    demo = None
    if settings.DEMO_AUTOFILL and cycle.status == "active" and not demo_autofill_service.ended(today):
        days = {l.log_date for l in logs}
        logged_today = {l.cycle_challenge_id for l in logs if l.log_date == today}
        phase = "recording"
        if len(days) >= demo_autofill_service.MIN_DAYS:
            phase = "finish_today" if today in days else "finish_only"
        demo = DemoInfo(record_days=len(days), phase=phase,
                        unlogged_today=sum(1 for cc, _ in missions if cc.cycle_challenge_id not in logged_today))

    return CycleResult(
        demo=demo,
        cycle_id=cycle.cycle_id, cycle_number=cycle.cycle_number, total_cycles=PROGRAM_CYCLES,
        status=cycle.status, started_on=cycle.started_on, ended_on=cycle.ended_on, today=today,
        day_number=day, week_number=rules.week_of(cycle.started_on, cycle.started_on + timedelta(days=day - 1)),
        missions=items,
    )


async def _sex(db: AsyncSession, user_id: str) -> str:
    profile = await user_repository.get_profile(db, user_id)
    return profile.sex if profile and profile.sex else "female"

def _program_is_complete(cycles: list[ChallengeCycle]) -> bool:
    """완료·미완료로 끝난 4주 사이클이 3개면 12주 프로그램 완료다."""
    finished = sum(
        1
        for cycle in cycles
        if cycle.status in ("completed", "incomplete")
    )
    return finished >= PROGRAM_CYCLES


async def get_program_status(db: AsyncSession, user_id: str) -> ProgramStatus:
    """가장 최근 12주 프로그램의 완료 여부와 모델 버전 안내."""
    program = await challenge_repository.get_latest_program(db, user_id)
    if program is None:
        raise AppError(404, "PROGRAM_NOT_FOUND", "아직 시작한 12주 프로그램이 없습니다.")

    cycles = await challenge_repository.get_program_cycles(db, program.program_id)
    complete = _program_is_complete(cycles)
    latest = predictor.current_program_model_info()

    version_changed = bool(
        (program.model_a_version and program.model_a_version != latest["model_a_version"])
        or (program.model_b_version and program.model_b_version != latest["model_b_version"])
    )

    return ProgramStatus(
        program_number=program.program_number,
        complete=complete,
        can_restart=complete,
        model_version=program.model_a_version,
        latest_model_version=latest["model_version"],
        version_changed=version_changed,
        latest_updated_on=latest["model_updated_on"],
        change_note=latest["change_note"],
        model_a_version=program.model_a_version,
        model_b_version=program.model_b_version,
    )


async def restart_program(db: AsyncSession, user_id: str) -> ProgramStatus:
    """완료한 12주 프로그램 뒤에 새 프로그램을 만들고 최신 모델 버전을 고정한다."""
    current = await challenge_repository.get_latest_program(db, user_id)
    if current is None:
        raise AppError(409, "PROGRAM_NOT_COMPLETE", "완료한 12주 프로그램이 없습니다.")

    cycles = await challenge_repository.get_program_cycles(db, current.program_id)
    if not _program_is_complete(cycles):
        raise AppError(409, "PROGRAM_NOT_COMPLETE", "12주를 모두 마친 뒤 새 프로그램을 시작할 수 있습니다.")

    latest = predictor.current_program_model_info()
    await challenge_repository.create_program(
        db=db,
        user_id=user_id,
        program_number=current.program_number + 1,
        model_a_version=latest["model_a_version"],
        model_b_version=latest["model_b_version"],
        model_updated_on=latest["model_updated_on"],
        change_note=latest["change_note"],
        now=utcnow(),
    )
    await db.commit()

    return await get_program_status(db, user_id)


async def get_current_cycle(db: AsyncSession, user_id: str) -> CycleResult:
    cycle = await _current_active(db, user_id)
    if cycle is None:
        raise AppError(404, "CHALLENGE_CYCLE_NOT_FOUND", "진행 중인 챌린지가 없습니다.")
    return await _cycle_result(db, cycle, await _sex(db, user_id), today_kst())


async def get_cycle(db: AsyncSession, user_id: str, cycle_id: str) -> CycleResult:
    cycle = await challenge_repository.get_cycle(db, cycle_id)
    if cycle is None or cycle.user_id != user_id:
        raise AppError(404, "CHALLENGE_CYCLE_NOT_FOUND", "챌린지를 찾을 수 없습니다.")
    await _finalize_if_ended(db, cycle, today_kst())
    return await _cycle_result(db, cycle, await _sex(db, user_id), today_kst())


async def list_cycles(db: AsyncSession, user_id: str) -> list[CycleSummary]:
    await _current_active(db, user_id)  # 끝난 사이클이 있으면 먼저 닫는다
    result = []
    cycles = await challenge_repository.get_cycles(db, user_id)
    programs = await challenge_repository.get_programs(db, user_id)
    program_numbers = {
        program.program_id: program.program_number
        for program in programs
    }
    reassessed = await challenge_repository.get_reassessed_cycle_ids(
        db,
        [c.cycle_id for c in cycles],
    )

    for cycle in cycles:
        missions = await challenge_repository.get_cycle_missions(db, cycle.cycle_id)
        logs = await challenge_repository.get_logs(db, [cc.cycle_challenge_id for cc, _ in missions])
        rates = [
            rules.progress(cycle.started_on, cc.weekly_target,
                           [(l.log_date, l.status) for l in logs if l.cycle_challenge_id == cc.cycle_challenge_id]
                           )["cycle_rate"]
            for cc, _ in missions
        ]
        result.append(CycleSummary(
            cycle_id=cycle.cycle_id, cycle_number=cycle.cycle_number, status=cycle.status,
            started_on=cycle.started_on, ended_on=cycle.ended_on,
            cycle_rate=sum(rates) / len(rates) if rates else 0.0,
            mission_codes=[ch.challenge_code for _, ch in missions],
            reassessed=cycle.cycle_id in reassessed,
            program_number=program_numbers[cycle.program_id],
        ))
    return result


# ---------------------------------------------------------------- W10 매일 기록
async def record_log(
    db: AsyncSession, user_id: str, code: str, answer: str | None, quantity: float | None, note: str | None
) -> LogResult:
    """오늘 기록을 저장한다. 오늘 기록이 이미 있으면 고친다 (당일만 수정, REQ-CHAL-005)."""
    cycle = await _current_active(db, user_id)
    if cycle is None:
        raise AppError(404, "CHALLENGE_CYCLE_NOT_FOUND", "진행 중인 챌린지가 없습니다.")
    missions = await challenge_repository.get_cycle_missions(db, cycle.cycle_id)
    match = next(((cc, ch) for cc, ch in missions if ch.challenge_code == code), None)
    if match is None:
        raise AppError(404, "CHALLENGE_MISSION_NOT_FOUND", "이번 챌린지에 없는 미션입니다.")
    cc, _ = match

    sex = await _sex(db, user_id)
    if code == "ALC-1" and quantity is None and answer is not None and answer.isdigit():
        quantity = int(answer)
    try:
        values = rules.evaluate_log(code, answer, quantity, sex, cc.target_config)
    except ValueError as e:
        raise AppError(422, "CHALLENGE_LOG_INVALID", str(e))

    today, now = today_kst(), utcnow()
    if settings.DEMO_AUTOFILL and not demo_autofill_service.ended(today):
        _, _, days = await demo_autofill_service.record_days(db, cycle)
        if today not in days and len(days) >= demo_autofill_service.MIN_DAYS:
            raise AppError(409, "DEMO_RECORDING_CLOSED", "체험 기록은 3일까지예요. 결과 보기를 눌러 4주 결과를 확인해 주세요.")
    log = await challenge_repository.get_log(db, cc.cycle_challenge_id, today)
    if log is None:
        log = challenge_repository.add_log(
            db, cc.cycle_challenge_id, today, {**values, "answer": answer, "note": note}, now
        )
    else:
        for k, v in {**values, "answer": answer, "note": note}.items():
            setattr(log, k, v)
        log.updated_at = now
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "CHALLENGE_LOG_DUPLICATED", "오늘 기록이 이미 있습니다. 다시 시도해 주세요.")
    await challenge_reward_service.reward_after_log(db, user_id, today)   # 오늘 모두 완료 +5, 5일마다 +10
    await db.commit()
    result = _log_result(log)
    result.autofill_pattern = await demo_autofill_service.maybe_autofill(db, cycle)   # 체험 모드(DEMO_AUTOFILL)에서만
    result.autofilled = result.autofill_pattern is not None
    return result

async def finish_demo(db: AsyncSession, user_id: str, confirm: bool) -> LogResult | dict:
    """체험: "오늘 기록 마치고 4주 결과 보기". 기록한 날이 3일이어야 하고, 오늘 기록하지 않은 미션이 있으면 confirm이 있어야 한다."""
    today = today_kst()
    if not settings.DEMO_AUTOFILL or demo_autofill_service.ended(today):
        raise AppError(409, "DEMO_NOT_AVAILABLE", "체험 기간이 끝났거나 체험 기능이 꺼져 있습니다.")
    cycle = await _current_active(db, user_id)
    if cycle is None:
        raise AppError(404, "CHALLENGE_CYCLE_NOT_FOUND", "진행 중인 챌린지가 없습니다.")
    # 두 요청이 겹치면 한쪽이 기다렸다가 먼저 채운 결과를 보게, 사이클 행을 잠근다
    cycle = (await db.execute(select(ChallengeCycle).where(ChallengeCycle.cycle_id == cycle.cycle_id)
                              .with_for_update().execution_options(populate_existing=True))).scalar_one()
    if cycle.status != "active":
        return {"cycle_id": cycle.cycle_id, "autofill_pattern": await demo_autofill_service.pattern_of(db, cycle.cycle_id)}
    missions, logs, days = await demo_autofill_service.record_days(db, cycle)
    if len(days) < demo_autofill_service.MIN_DAYS:
        raise AppError(409, "DEMO_NOT_READY", "서로 다른 3일을 기록하면 결과를 볼 수 있어요.")
    logged_today = {l.cycle_challenge_id for l in logs if l.log_date == today}
    if today in days and not confirm and any(cc.cycle_challenge_id not in logged_today for cc, _ in missions):
        raise AppError(409, "DEMO_MISSIONS_UNLOGGED", "오늘 기록하지 않은 미션이 있어요.")
    pattern = await demo_autofill_service.maybe_autofill(db, cycle, finish=True)
    if pattern is None:     # 빠르게 두 번 눌러 이미 채워졌다면 먼저 채운 결과를 돌려준다
        pattern = await demo_autofill_service.pattern_of(db, cycle.cycle_id)
    return {"cycle_id": cycle.cycle_id, "autofill_pattern": pattern}


async def demo_status(db: AsyncSession, user_id: str) -> DemoStatus:
    """체험 종료 안내용: 체험이 끝났는지, 이 사용자가 자동 채움 결과를 받았는지."""
    today = today_kst()
    has_result = False
    for cycle in await challenge_repository.get_cycles(db, user_id):
        if await demo_autofill_service.pattern_of(db, cycle.cycle_id):
            has_result = True
            break
    return DemoStatus(enabled=settings.DEMO_AUTOFILL, ended=demo_autofill_service.ended(today),
                      ends_on=settings.demo_end, has_result=has_result)


async def stop_cycle(db: AsyncSession, user_id: str, reason_code: str | None, note: str | None) -> CycleResult:
    """진행 중인 사이클 중단 (REQ-CHAL-007). 중단한 사이클은 사이클 번호를 쓰지 않는다."""
    cycle = await _current_active(db, user_id)
    if cycle is None:
        raise AppError(404, "CHALLENGE_CYCLE_NOT_FOUND", "진행 중인 챌린지가 없습니다.")
    for cc, _ in await challenge_repository.get_cycle_missions(db, cycle.cycle_id):
        cc.status = "stopped"
    cycle.status, cycle.stopped_reason_code, cycle.stopped_note = "stopped", reason_code, note
    cycle.updated_at = utcnow()
    await db.commit()
    return await _cycle_result(db, cycle, await _sex(db, user_id), today_kst())


# ---------------------------------------------------------------- 4주 재입력 → 재예측 → 전후 비교 (가이드 §6, W11-2)
# 다시 받는 항목 (§6.1). 나머지는 재예측 때 예측 서비스가 직전 기록에서 가져온다 (carried_forward)
REASSESS_REQUIRED = {"SBP", "DBP", "WEIGHT", "SMOKING", "ALCOHOL_FREQ"}
REASSESS_ALLOWED = REASSESS_REQUIRED | {"WAIST", "ALCOHOL_AMOUNT", "ECIG"}
BP_NOTE = "한 번 잰 값이라 차이가 작으면 측정 오차일 수 있어요."


async def _owned_ended_cycle(db: AsyncSession, user_id: str, cycle_id: str) -> ChallengeCycle:
    cycle = await challenge_repository.get_cycle(db, cycle_id)
    if cycle is None or cycle.user_id != user_id:
        raise AppError(404, "CHALLENGE_CYCLE_NOT_FOUND", "챌린지를 찾을 수 없습니다.")
    await _finalize_if_ended(db, cycle, today_kst())
    return cycle


async def submit_reassessment(db: AsyncSession, user_id: str, cycle_id: str, exam_date: date | None,
                              items: list[dict]) -> ReviewResult:
    """4주 재입력 저장 → 모델 A·B 재예측(interim, 직전 값 이월은 예측 서비스가 함) → 전후 비교."""
    cycle = await _owned_ended_cycle(db, user_id, cycle_id)
    program = await challenge_repository.get_program_by_id(db, cycle.program_id)
    if program is None:
        raise AppError(500, "PROGRAM_NOT_FOUND", "사이클의 12주 프로그램 정보를 찾을 수 없습니다.")

    # 이전 데이터에는 버전이 비어 있을 수 있어 최신값으로 안전하게 보완한다.
    model_versions = {
        "MODEL_A": program.model_a_version or predictor.CURRENT_VERSION["MODEL_A"],
        "MODEL_B": program.model_b_version or predictor.CURRENT_VERSION["MODEL_B"],
    }
    if cycle.status in ("active", "stopped"):
        raise AppError(409, "CHALLENGE_CYCLE_NOT_ENDED", "4주가 끝난 챌린지만 재입력할 수 있습니다.")
    if await challenge_repository.get_reassessment(db, cycle.cycle_id) is not None:
        raise AppError(409, "REASSESSMENT_DUPLICATED", "이 사이클의 4주 재입력은 이미 했습니다.")

    codes = [i["metric_code"] for i in items]
    if len(set(codes)) != len(codes):
        raise AppError(422, "HEALTH_METRIC_DUPLICATED", "한 번에 같은 지표를 두 번 보냈습니다.")
    unknown = set(codes) - REASSESS_ALLOWED
    if unknown:
        raise AppError(422, "REASSESSMENT_METRIC_INVALID", f"4주 재입력에서 받지 않는 항목입니다: {', '.join(sorted(unknown))}")
    missing = REASSESS_REQUIRED - set(codes)
    if missing:
        raise AppError(422, "REASSESSMENT_INCOMPLETE", f"입력하지 않은 항목이 있습니다: {', '.join(sorted(missing))}")
    checked = [health_service._check_item(i) for i in items]
    freq = next(c for c in checked if c["metric_code"] == "ALCOHOL_FREQ")["value_code"]
    if freq in health_service.NON_DRINKER and "ALCOHOL_AMOUNT" in codes:
        raise AppError(422, "HEALTH_ALCOHOL_AMOUNT_NOT_ALLOWED", "술을 마시지 않으면 음주량은 보내지 않습니다.")

    basis = await challenge_repository.get_basis_record(db, user_id, cycle.started_on, cycle.cycle_id)
    if basis is None:
        raise AppError(409, "HEALTH_RECORD_REQUIRED", "처음 입력한 건강정보가 없습니다.")
    first = await challenge_repository.get_measurement_map(db, basis.health_record_id)    # 키는 처음 값을 그대로 쓴다
    health_service.check_consistency(checked, {k: m.value_num for k, m in first.items() if k == "HEIGHT" and m.value_num is not None})
    schema = await health_repository.get_active_schema(db)
    if schema is None:
        raise AppError(500, "HEALTH_SCHEMA_NOT_FOUND", "입력 양식 설정이 없습니다. 관리자에게 문의해 주세요.")
    now = utcnow()
    record = await health_repository.create_health_record(
        db, user_id, schema.health_schema_id, "interim_reassessment", exam_date or today_kst(), now
    )
    record.cycle_id = cycle.cycle_id
    await health_repository.create_measurements(db, record.health_record_id, record.examination_date, checked, now)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "HEALTH_RECORD_DUPLICATED", "같은 날짜에 같은 종류의 기록이 이미 있습니다.")

    # 재예측(interim): 다시 받지 않은 항목(키·콜레스테롤·당뇨·고혈압 진단·가족력)은 예측 서비스가 직전 값으로 채운다
    # (prediction_job_service._carry_forward). 모델 하나가 실패해도 결과는 "failed"로 저장되고 비교 화면은 그대로 보여준다
    await prediction_job_service.create_job(
        db,
        user_id,
        record.health_record_id,
        None,
        "interim",
        model_versions=model_versions,
    )
    return await get_review(db, user_id, cycle_id)


def _snapshot(record, m: dict) -> Snapshot:
    def num(code):
        return m[code].value_num if code in m else None

    def code_(code):
        return m[code].value_code if code in m else None

    return Snapshot(
        examination_date=record.examination_date, sbp=num("SBP"), dbp=num("DBP"), weight_kg=num("WEIGHT"),
        waist_cm=num("WAIST"), smoking=code_("SMOKING"), drink_freq=code_("ALCOHOL_FREQ"),
        drink_amount=code_("ALCOHOL_AMOUNT"),
    )

async def _model_changes(db: AsyncSession, before_p: dict, after_p: dict) -> list[ModelChange]:
    """모델 A·B 전·후. 버전이 다르면 입력값 사진으로 지금 모델로 다시 계산해서 같은 모델끼리 비교하고,
    비교할 수 없으면 reason으로 이유를 알린다 (4주 리뷰와 12주 리뷰가 같이 쓴다)."""
    models = []
    for code in ("MODEL_A", "MODEL_B"):
        b = before_p.get(code)
        a = after_p.get(code)
        reason = prediction_job_service.comparison_reason(b, a)
        models.append(ModelChange(
            model_code=code,
            before_status=b.status if b else None, before_risk_level=b.risk_level if b else None,
            before_probability=b.score if b else None,
            after_status=a.status if a else None, after_risk_level=a.risk_level if a else None,
            after_probability=a.score if a else None,
            model_version=(a or b).model_version if (a or b) else None,
            comparable=reason is None,
            reason=reason,
            before_similarity_level=similarity_level_b(b.score, b.model_version)
            if b and code == "MODEL_B" and b.status == "completed" else None,
            after_similarity_level=similarity_level_b(a.score, a.model_version)
            if a and code == "MODEL_B" and a.status == "completed" else None,
            before_percentile=getattr(b, "percentile", None) if b and code == "MODEL_A" else None,
            after_percentile=getattr(a, "percentile", None) if a and code == "MODEL_A" else None,
        ))
    return models


async def get_review(db: AsyncSession, user_id: str, cycle_id: str) -> ReviewResult:
    """W11-2 전후 비교: 혈압·몸무게·허리둘레·미션 달성률·습관·모델 결과 (같은 모델 버전만)."""
    cycle = await _owned_ended_cycle(db, user_id, cycle_id)
    sex = await _sex(db, user_id)
    basis = await challenge_repository.get_basis_record(db, user_id, cycle.started_on, cycle.cycle_id)
    after = await challenge_repository.get_reassessment(db, cycle.cycle_id)
    before_m = await challenge_repository.get_measurement_map(db, basis.health_record_id) if basis else {}
    after_m = await challenge_repository.get_measurement_map(db, after.health_record_id) if after else {}

    detail = await _cycle_result(db, cycle, sex, today_kst())
    height = (before_m.get("HEIGHT") or after_m.get("HEIGHT"))
    rng = rules.normal_weight_range(height.value_num) if height and height.value_num else None

    before_p = {p.model_code: p for p in await challenge_repository.get_latest_job_predictions(db, basis.health_record_id)} if basis else {}
    after_p = {p.model_code: p for p in await challenge_repository.get_latest_job_predictions(db, after.health_record_id)} if after else {}
    models = await _model_changes(db, before_p, after_p)

    return ReviewResult(
        cycle_id=cycle.cycle_id, cycle_number=cycle.cycle_number, total_cycles=PROGRAM_CYCLES,
        cycle_status=cycle.status, reassessed=after is not None,
        before=_snapshot(basis, before_m) if basis else None,
        after=_snapshot(after, after_m) if after else None,
        missions=[MissionResult(code=m.card.code, name=m.card.name, status=m.status, cycle_rate=m.cycle_rate)
                  for m in detail.missions],
        normal_weight_range=list(rng) if rng else None,
        waist_limit=rules.waist_limit(sex),
        models=models,
        bp_note=BP_NOTE,
        demo_fill=await demo_autofill_service.pattern_of(db, cycle.cycle_id),
    )
async def get_program_review(
    db: AsyncSession,
    user_id: str,
    program_number: int | None = None,
) -> ProgramReviewResult:
    """12주 프로그램의 처음(0주) ↔ 지금까지(마지막 재입력) 비교.
    처음 = 1차 사이클을 시작할 때 기준이 된 건강기록, 마지막 = 지금까지 한 사이클 끝 재입력 중 가장 나중 것(4·8·12주).
    12주를 다 못 채웠거나 중간에 그만둔 사람도 재입력이 하나라도 있으면 '지금까지'를 보여 준다 (weeks_done).
    모델 결과는 _model_changes로 같은 모델 버전끼리 비교한다(버전이 다르면 입력값 사진으로 다시 계산, 나이는 처음 나이).
    재입력이 하나도 없으면 PROGRAM_REVIEW_NOT_READY."""
    await _current_active(db, user_id)                                  # 끝난 사이클이 있으면 먼저 닫는다
    program = (
        await challenge_repository.get_program(db, user_id, program_number)
        if program_number is not None
        else await challenge_repository.get_latest_program(db, user_id)
    )
    if program is None:
        raise AppError(404, "PROGRAM_NOT_FOUND", "12주 프로그램을 찾을 수 없습니다.")

    cycles = await challenge_repository.get_program_cycles(db, program.program_id)
    first = cycles[0] if cycles else None
    basis = await challenge_repository.get_basis_record(db, user_id, first.started_on, first.cycle_id) if first else None

    reassessed = []                                                      # (사이클, 그 사이클 끝 재입력)
    for c in cycles:
        r = await challenge_repository.get_reassessment(db, c.cycle_id)
        if r is not None:
            reassessed.append((c, r))
    if basis is None or not reassessed:
        raise AppError(404, "PROGRAM_REVIEW_NOT_READY", "첫 4주 재입력을 마치면 볼 수 있어요.")
    last_cycle, final = reassessed[-1]

    before_m = await challenge_repository.get_measurement_map(db, basis.health_record_id)
    after_m = await challenge_repository.get_measurement_map(db, final.health_record_id)
    checkpoints = [ProgramCheckpoint(week=0, **_snapshot(basis, before_m).model_dump())]
    for c, r in reassessed:
        m = await challenge_repository.get_measurement_map(db, r.health_record_id)
        checkpoints.append(ProgramCheckpoint(week=c.cycle_number * CYCLE_WEEKS, **_snapshot(r, m).model_dump()))

    rates = {s.cycle_id: s.cycle_rate for s in await list_cycles(db, user_id)}
    before_p = {p.model_code: p for p in await challenge_repository.get_latest_job_predictions(db, basis.health_record_id)}
    after_p = {p.model_code: p for p in await challenge_repository.get_latest_job_predictions(db, final.health_record_id)}
    return ProgramReviewResult(
        program_number=program.program_number,
        model_version=program.model_a_version,
        model_updated_on=program.model_updated_on,
        weeks_done=last_cycle.cycle_number * CYCLE_WEEKS,
        before=_snapshot(basis, before_m), after=_snapshot(final, after_m), checkpoints=checkpoints,
        cycles=[ProgramCycleRate(cycle_number=c.cycle_number, status=c.status, cycle_rate=rates.get(c.cycle_id, 0.0))
                for c in cycles],
        models=await _model_changes(db, before_p, after_p),
        bp_note=BP_NOTE,
    )