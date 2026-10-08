"""건강기록 창고 담당. DB에 넣고 꺼내는 일만 한다."""
from sqlalchemy import select,delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime
from app.models.health import HealthInputSchema, HealthRecord, HealthMeasurement


async def get_active_schema(db: AsyncSession) -> HealthInputSchema | None:
    """지금 쓰는 입력 양식 버전 (그만 쓴 날짜가 비어 있는 것 중 가장 최근)."""
    result = await db.execute(
        select(HealthInputSchema)
        .where(HealthInputSchema.retired_at.is_(None))
        .order_by(HealthInputSchema.active_from.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()

async def create_health_record(
    db: AsyncSession,
    user_id: str,
    health_schema_id: str,
    input_type: str,
    examination_date: date,
    now: datetime,
) -> HealthRecord:
    """상자를 만든다. 저장 확정(commit)은 서비스가 한다."""
    record = HealthRecord(
        user_id=user_id,
        health_schema_id=health_schema_id,
        input_type=input_type,
        examination_date=examination_date,
        created_at=now,
    )
    db.add(record)
    await db.flush()
    return record

async def get_health_record(db: AsyncSession, health_record_id: str) -> HealthRecord | None:
    """상자 번호로 상자를 찾는다. 없으면 None."""
    return await db.get(HealthRecord, health_record_id)

async def create_measurements(
    db: AsyncSession, health_record_id: str, measured_on: date, items: list[dict], now: datetime
) -> list[HealthMeasurement]:
    """상자에 물건 여러 개를 넣는다. 저장 확정(commit)은 서비스가 한다."""
    created = []
    for item in items:
        m = HealthMeasurement(
            health_record_id=health_record_id,
            metric_code=item["metric_code"],
            value_num=item.get("value_num"),
            value_code=item.get("value_code"),
            unit=item.get("unit"),
            measured_on=measured_on,
            input_method=item.get("input_method", "manual"),
            source_measurement_id=item.get("source_measurement_id"),
            created_at=now,
        )
        db.add(m)
        created.append(m)
    return created

async def get_measurements(db: AsyncSession, health_record_id: str) -> list[HealthMeasurement]:
    """📦 상자 안의 물건을 전부 꺼낸다."""
    result = await db.execute(
        select(HealthMeasurement).where(HealthMeasurement.health_record_id == health_record_id)
    )
    return list(result.scalars().all())

async def get_records_by_user(db: AsyncSession, user_id: str, limit: int = 20) -> list[HealthRecord]:
    """📦 내 상자들, 최근 검진부터."""
    result = await db.execute(
        select(HealthRecord)
        .where(HealthRecord.user_id == user_id)
        .order_by(HealthRecord.examination_date.desc(), HealthRecord.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())

async def delete_measurements(db: AsyncSession, health_record_id: str, metric_codes: list[str]) -> None:
    """📦 이 상자에서, 이 지표들의 예전 물건을 뺀다 (값 바꾸기용)."""
    await db.execute(
        delete(HealthMeasurement)
        .where(HealthMeasurement.health_record_id == health_record_id)
        .where(HealthMeasurement.metric_code.in_(metric_codes))
    )

async def get_previous_measurements(
    db: AsyncSession, user_id: str, exclude_record_id: str, metric_codes: list[str]
) -> list[HealthMeasurement]:
    """📦 내 다른 상자들에서, 이 지표들의 물건을 최근 검진부터 꺼낸다 (4주 재평가 이월용)."""
    if not metric_codes:
        return []
    result = await db.execute(
        select(HealthMeasurement)
        .join(HealthRecord, HealthRecord.health_record_id == HealthMeasurement.health_record_id)
        .where(HealthRecord.user_id == user_id)
        .where(HealthRecord.health_record_id != exclude_record_id)
        .where(HealthMeasurement.metric_code.in_(metric_codes))
        .order_by(HealthRecord.examination_date.desc(), HealthRecord.created_at.desc())
    )
    return list(result.scalars().all())