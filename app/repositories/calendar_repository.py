"""캘린더 창고 담당. DB에 넣고 꺼내는 일만 한다."""
from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar import CalendarEntry, HealthTodo


async def get_entry(db: AsyncSession, user_id: str, entry_date: date) -> CalendarEntry | None:
    result = await db.execute(
        select(CalendarEntry).where(CalendarEntry.user_id == user_id, CalendarEntry.entry_date == entry_date)
    )
    return result.scalar_one_or_none()


async def create_entry(db: AsyncSession, user_id: str, entry_date: date, now: datetime) -> CalendarEntry:
    entry = CalendarEntry(user_id=user_id, entry_date=entry_date, created_at=now, updated_at=now)
    db.add(entry)
    await db.flush()
    return entry


async def list_entries(db: AsyncSession, user_id: str, start: date, end: date) -> list[CalendarEntry]:
    """start 이상 end 미만."""
    result = await db.execute(
        select(CalendarEntry)
        .where(CalendarEntry.user_id == user_id, CalendarEntry.entry_date >= start, CalendarEntry.entry_date < end)
        .order_by(CalendarEntry.entry_date)
    )
    return list(result.scalars().all())


async def delete_entry(db: AsyncSession, entry: CalendarEntry) -> None:
    await db.delete(entry)


async def list_todos(db: AsyncSession, user_id: str, start: date, end: date) -> list[HealthTodo]:
    result = await db.execute(
        select(HealthTodo)
        .where(HealthTodo.user_id == user_id, HealthTodo.todo_date >= start, HealthTodo.todo_date < end)
        .order_by(HealthTodo.todo_date, HealthTodo.created_at)
    )
    return list(result.scalars().all())


async def count_todos(db: AsyncSession, user_id: str, todo_date: date) -> int:
    result = await db.execute(
        select(func.count()).select_from(HealthTodo).where(HealthTodo.user_id == user_id, HealthTodo.todo_date == todo_date)
    )
    return int(result.scalar_one())


async def create_todo(db: AsyncSession, user_id: str, todo_date: date, text: str, now: datetime) -> HealthTodo:
    todo = HealthTodo(user_id=user_id, todo_date=todo_date, text=text, done=False, created_at=now)
    db.add(todo)
    await db.flush()
    return todo


async def get_todo(db: AsyncSession, todo_id: str) -> HealthTodo | None:
    return await db.get(HealthTodo, todo_id)


async def delete_todo(db: AsyncSession, todo: HealthTodo) -> None:
    await db.delete(todo)
