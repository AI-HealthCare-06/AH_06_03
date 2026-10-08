"""챌린지 매니저. 건강정보·설문을 꺼내 판정하고, 사이클·매일 기록을 저장한다.

규칙은 app/services/challenge_rules.py, 문구는 app/services/challenge_catalog.py.
"""
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.challenge import ChallengeCycle
from app.repositories import challenge_repository, survey_repository, user_repository
from app.schemas.challenge import (
    AnswerOption, CycleMission, CycleResult, CycleSummary, ExcludedItem, FixedSlot, LogResult, MissionCard,
    RecommendationResult, SodiumResult, SurveyNeeded, WeekProgress,
)
from app.services import challenge_rules as rules
from app.services.challenge_catalog import (
    CATEGORY_NAMES, CYCLE_DAYS, KEEP_GOING_MESSAGE, MISSION_COMPLETE_RATE, MISSIONS, PROGRAM_CYCLES,
    SELECTABLE_NOTICE,
)
from app.services.model_input import age_on

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
    answers = {q: o for q, (o, _) in raw.items()}
    scores = {q: s for q, (_, s) in raw.items() if q in rules.NA_QUESTIONS and s is not None}

    diabetes = code_("DIABETES")
    facts = rules.UserFacts(
        age=age_on(profile.birth_date, record.examination_date), sex=profile.sex,
        smoking=code_("SMOKING"), ecig=code_("ECIG"),
        drink_freq=code_("ALCOHOL_FREQ"), drink_amount=code_("ALCOHOL_AMOUNT"),
        sbp=num("SBP"), dbp=num("DBP"), height_cm=num("HEIGHT"), weight_kg=num("WEIGHT"),
        htn_status=code_("HTN_STATUS"), diabetes=None if diabetes is None else diabetes == "true",
        answers=answers, scores=scores,
        baseline_steps=None,  # P2 걸음 수: 설문 v2에서 숫자 응답이 저장되면 연결
    )
    return facts, record, instance


async def _active_codes(db: AsyncSession) -> tuple[set[str], dict]:
    """관리자가 노출 중인 미션 코드, 미션별 (Challenge, Level)."""
    rows = await challenge_repository.get_catalog(db)
    active = {ch.challenge_code for ch, cat, _ in rows if ch.active and cat.active}
    return active, {ch.challenge_code: (ch, lv) for ch, _, lv in rows}


async def _next_cycle_number(db: AsyncSession, user_id: str) -> int:
    cycles = await challenge_repository.get_cycles(db, user_id)
    return sum(1 for c in cycles if c.status in ("completed", "incomplete")) + 1


async def _build_recommendation(db: AsyncSession, user_id: str):
    facts, record, instance = await _load_facts(db, user_id)
    c = rules.classify(facts)
    completed = await challenge_repository.get_completed_codes(db, user_id)
    rec = rules.recommend(c, facts.answers, completed)
    active, _ = await _active_codes(db)
    rec.candidates = [code for code in rec.candidates if code in active]
    return facts, record, instance, c, rec


# ---------------------------------------------------------------- W09 추천
async def get_recommendation(db: AsyncSession, user_id: str) -> RecommendationResult:
    facts, _, _, c, rec = await _build_recommendation(db, user_id)
    sodium = c.get("sodium")
    done = set(rec.completed)
    return RecommendationResult(
        cycle_number=await _next_cycle_number(db, user_id),
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

    facts, record, instance, c, rec = await _build_recommendation(db, user_id)
    if selected_code not in rec.candidates:
        raise AppError(422, "CHALLENGE_SELECTION_INVALID", "선택할 수 없는 미션입니다.")

    _, catalog = await _active_codes(db)
    chosen = [(s["code"], s["selection_type"]) for s in rec.fixed if s["code"]] + [(selected_code, "selected")]

    now, today = utcnow(), today_kst()
    cycle = await challenge_repository.create_cycle(
        db, user_id, await _next_cycle_number(db, user_id), today, today + timedelta(days=CYCLE_DAYS - 1), now
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

    return CycleResult(
        cycle_id=cycle.cycle_id, cycle_number=cycle.cycle_number, total_cycles=PROGRAM_CYCLES,
        status=cycle.status, started_on=cycle.started_on, ended_on=cycle.ended_on, today=today,
        day_number=day, week_number=rules.week_of(cycle.started_on, cycle.started_on + timedelta(days=day - 1)),
        missions=items,
    )


async def _sex(db: AsyncSession, user_id: str) -> str:
    profile = await user_repository.get_profile(db, user_id)
    return profile.sex if profile and profile.sex else "female"


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
    for cycle in await challenge_repository.get_cycles(db, user_id):
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
    return _log_result(log)


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
