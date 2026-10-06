"""건강기록 매니저. 판단(양식 버전, 중복, 내 상자인지, 값 검사)을 한다."""
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.repositories import health_repository, prediction_repository
from app.schemas.health import HealthRecordResult, MeasurementResult

# 정해진 지표 이름 (ERD v9, 모델_연결_명세 §1.2)
# "num" = 재는 값 (value_num, 단위 필요) / "code" = 고르는 값 (value_code, 정해진 보기 중 하나)
METRICS = {
    "SBP":             ("num", "mmHg"),
    "DBP":             ("num", "mmHg"),
    "HEIGHT":          ("num", "cm"),
    "WEIGHT":          ("num", "kg"),
    "WAIST":           ("num", "cm"),
    "TOTAL_CHOL":      ("num", "mg/dL"),
    "HDL":             ("num", "mg/dL"),
    "FASTING_GLUCOSE": ("num", "mg/dL"),
    "SMOKING":         ("code", {"current", "former", "never"}),
    "DIABETES":        ("code", {"true", "false"}),
    "HTN_STATUS":      ("code", {"none", "diagnosed_untreated", "treated"}),
    "PARENT_HTN":      ("code", {"yes", "no", "unknown"}),
    "ALCOHOL_FREQ":    ("code", {"never_lifetime", "none_past_year", "lt_monthly", "monthly",
                                 "2_4_per_month", "2_3_per_week", "4plus_per_week"}),
    "ALCOHOL_AMOUNT":  ("code", {"1_2", "3_4", "5_6", "7_9", "10plus"}),
}


async def create_record(db: AsyncSession, user_id: str, input_type: str, examination_date: date) -> HealthRecordResult:
    schema = await health_repository.get_active_schema(db)
    if schema is None:
        raise AppError(500, "HEALTH_SCHEMA_NOT_FOUND", "입력 양식 설정이 없습니다. 관리자에게 문의해 주세요.")

    try:
        record = await health_repository.create_health_record(
            db, user_id, schema.health_schema_id, input_type, examination_date, utcnow()
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "HEALTH_RECORD_DUPLICATED", "같은 날짜에 같은 종류의 기록이 이미 있습니다.")

    return HealthRecordResult(
        health_record_id=record.health_record_id,
        input_type=record.input_type,
        examination_date=record.examination_date,
    )

async def _get_my_record(db: AsyncSession, user_id: str, health_record_id: str):
    """내 상자면 돌려주고, 없거나 남의 상자면 똑같이 404."""
    record = await health_repository.get_health_record(db, health_record_id)
    if record is None or record.user_id != user_id:
        raise AppError(404, "HEALTH_RECORD_NOT_FOUND", "건강기록을 찾을 수 없습니다.")
    return record

def _check_one_value(item: dict) -> None:
    """value_num과 value_code 중 딱 하나만 있어야 한다."""
    has_num = item.get("value_num") is not None
    has_code = item.get("value_code") is not None
    if has_num == has_code:
        raise AppError(422, "HEALTH_VALUE_INVALID", f"{item['metric_code']}: 숫자 값과 범주 값 중 하나만 보내 주세요.")

def _check_item(item: dict) -> dict:
    """물건 하나를 METRICS 표와 비교해서 검사하고, 단위를 채워서 돌려준다."""
    code = item["metric_code"]
    if code not in METRICS:
        raise AppError(422, "HEALTH_METRIC_UNKNOWN", f"{code}: 알 수 없는 지표입니다.")

    _check_one_value(item)
    kind, rule = METRICS[code]

    if kind == "num":
        if item.get("value_num") is None:
            raise AppError(422, "HEALTH_VALUE_INVALID", f"{code}: 숫자 값으로 보내 주세요.")
        return {**item, "unit": rule}

    if item.get("value_code") not in rule:
        raise AppError(422, "HEALTH_VALUE_INVALID", f"{code}: 허용되지 않는 값입니다.")
    return {**item, "unit": None}

def _bmi_item(items: list[dict]) -> dict | None:
    """키와 몸무게가 둘 다 있으면 BMI 물건을 만든다. 없으면 None."""
    values = {i["metric_code"]: i.get("value_num") for i in items}
    height_cm, weight_kg = values.get("HEIGHT"), values.get("WEIGHT")
    if height_cm is None or weight_kg is None:
        return None

    height_m = height_cm / 100
    bmi = weight_kg / (height_m * height_m)
    return {"metric_code": "BMI", "value_num": round(bmi, 1), "unit": "kg/m2", "input_method": "calculated"}

async def add_measurements(
    db: AsyncSession, user_id: str, health_record_id: str, items: list[dict]
) -> list[MeasurementResult]:
    """물건 넣기. 같은 지표가 다시 오면 새 값으로 바꾼다. 예측에 쓴 상자는 잠근다."""
    # 1. 내 상자인가?
    record = await _get_my_record(db, user_id, health_record_id)

    # 2. 예측에 쓴 상자인가? → 잠금
    if await prediction_repository.is_record_used(db, record.health_record_id):
        raise AppError(409, "HEALTH_RECORD_LOCKED", "이미 예측에 사용된 건강기록은 고칠 수 없습니다.")

    # 3. 값 검사
    checked = [_check_item(item) for item in items]
    codes = [c["metric_code"] for c in checked]
    if len(set(codes)) != len(codes):
        raise AppError(422, "HEALTH_METRIC_DUPLICATED", "한 번에 같은 지표를 두 번 보냈습니다.")

    # 4. BMI 다시 계산: 상자에 남을 값 + 이번에 온 값
    existing = await health_repository.get_measurements(db, record.health_record_id)
    kept = [
        {"metric_code": m.metric_code, "value_num": m.value_num}
        for m in existing
        if m.metric_code not in codes and m.metric_code != "BMI"
    ]
    bmi = _bmi_item(kept + checked)

    # 5. 예전 물건 빼기 (바뀌는 지표 + BMI를 새로 계산했으면 예전 BMI도)
    to_delete = codes + (["BMI"] if bmi is not None else [])
    await health_repository.delete_measurements(db, record.health_record_id, to_delete)
    if bmi is not None:
        checked.append(bmi)

    # 6. 새 물건 넣기 → 진짜 저장
    try:
        created = await health_repository.create_measurements(
            db, record.health_record_id, record.examination_date, checked, utcnow()
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "HEALTH_MEASUREMENT_DUPLICATED", "이미 입력된 지표가 있습니다.")

    return [
        MeasurementResult(
            measurement_id=m.measurement_id,
            metric_code=m.metric_code,
            value_num=m.value_num,
            value_code=m.value_code,
            unit=m.unit,
            input_method=m.input_method,
        )
        for m in created
    ]

async def list_records(db: AsyncSession, user_id: str) -> list[HealthRecordResult]:
    """내 건강기록 목록 (최근 검진부터)."""
    records = await health_repository.get_records_by_user(db, user_id)
    return [
        HealthRecordResult(
            health_record_id=r.health_record_id,
            input_type=r.input_type,
            examination_date=r.examination_date,
        )
        for r in records
    ]