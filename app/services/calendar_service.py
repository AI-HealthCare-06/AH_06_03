"""캘린더 매니저. 판단(내 것인지, 개수 제한, 비어 있으면 지우기)을 한다."""
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.repositories import calendar_repository as repo
from app.schemas.calendar import CalendarDayResult, CalendarMonthDay, TodoResult

MAX_TODOS_PER_DAY = 30


def _month_range(month: str) -> tuple[date, date]:
    """'2026-10' → (2026-10-01, 2026-11-01)."""
    try:
        year, mon = (int(x) for x in month.split("-"))
        start = date(year, mon, 1)
    except (ValueError, TypeError):
        raise AppError(422, "CALENDAR_MONTH_INVALID", "월은 2026-10 형식으로 보내 주세요.")
    end = date(year + (mon == 12), (mon % 12) + 1, 1)
    return start, end


def _todo_result(t) -> TodoResult:
    return TodoResult(todo_id=t.todo_id, todo_date=t.todo_date, text=t.text, done=t.done)


async def list_month(db: AsyncSession, user_id: str, month: str) -> list[CalendarMonthDay]:
    """그 달에 일기·사진·할 일이 하나라도 있는 날만 날짜순으로."""
    start, end = _month_range(month)
    entries = {e.entry_date: e for e in await repo.list_entries(db, user_id, start, end)}
    todos: dict[date, list] = {}
    for t in await repo.list_todos(db, user_id, start, end):
        todos.setdefault(t.todo_date, []).append(t)
    days = []
    for d in sorted(set(entries) | set(todos)):
        e = entries.get(d)
        days.append(CalendarMonthDay(
            entry_date=d,
            diary=e.diary if e else None,
            has_photo=bool(e and e.photo_data),
            todos=[_todo_result(t) for t in todos.get(d, [])],
        ))
    return days


async def get_day(db: AsyncSession, user_id: str, day: date) -> CalendarDayResult:
    """하루치 전체 (사진 포함). 기록이 없으면 빈 하루를 돌려준다."""
    e = await repo.get_entry(db, user_id, day)
    todos = [_todo_result(t) for t in await repo.list_todos(db, user_id, day, date.fromordinal(day.toordinal() + 1))]
    return CalendarDayResult(entry_date=day, diary=e.diary if e else None, photo=e.photo_data if e else None, todos=todos)


async def save_entry(db: AsyncSession, user_id: str, entry_date: date, fields: dict) -> CalendarDayResult:
    """일기·사진 저장. fields에 든 키만 바꾼다 (photo=None이면 사진 삭제). 둘 다 비면 그날 기록을 지운다."""
    entry = await repo.get_entry(db, user_id, entry_date)
    if entry is None:
        try:
            entry = await repo.create_entry(db, user_id, entry_date, utcnow())
        except IntegrityError:   # 같은 날짜를 동시에 처음 저장한 경우: 먼저 들어간 행을 가져다 쓴다
            await db.rollback()
            entry = await repo.get_entry(db, user_id, entry_date)
    if "diary" in fields:
        entry.diary = (fields["diary"] or "").strip() or None
    if "photo" in fields:
        entry.photo_data = fields["photo"]
    entry.updated_at = utcnow()
    if entry.diary is None and entry.photo_data is None:
        await repo.delete_entry(db, entry)
        await db.commit()
        diary = photo = None
    else:
        await db.commit()
        diary, photo = entry.diary, entry.photo_data
    todos = [_todo_result(t) for t in await repo.list_todos(db, user_id, entry_date, date.fromordinal(entry_date.toordinal() + 1))]
    return CalendarDayResult(entry_date=entry_date, diary=diary, photo=photo, todos=todos)


async def add_todo(db: AsyncSession, user_id: str, todo_date: date, text: str) -> TodoResult:
    text = text.strip()
    if not text:
        raise AppError(422, "CALENDAR_TODO_EMPTY", "할 일을 입력해 주세요.")
    if await repo.count_todos(db, user_id, todo_date) >= MAX_TODOS_PER_DAY:
        raise AppError(409, "CALENDAR_TODO_LIMIT", f"하루에 할 일은 {MAX_TODOS_PER_DAY}개까지 넣을 수 있어요.")
    todo = await repo.create_todo(db, user_id, todo_date, text, utcnow())
    await db.commit()
    return _todo_result(todo)


async def _get_my_todo(db: AsyncSession, user_id: str, todo_id: str):
    """내 것이면 돌려주고, 없거나 남의 것이면 똑같이 404."""
    todo = await repo.get_todo(db, todo_id)
    if todo is None or todo.user_id != user_id:
        raise AppError(404, "CALENDAR_TODO_NOT_FOUND", "할 일을 찾을 수 없습니다.")
    return todo


async def update_todo(db: AsyncSession, user_id: str, todo_id: str, fields: dict) -> TodoResult:
    todo = await _get_my_todo(db, user_id, todo_id)
    if fields.get("text") is not None:
        text = fields["text"].strip()
        if not text:
            raise AppError(422, "CALENDAR_TODO_EMPTY", "할 일을 입력해 주세요.")
        todo.text = text
    if fields.get("done") is not None:
        todo.done = fields["done"]
    await db.commit()
    return _todo_result(todo)


async def remove_todo(db: AsyncSession, user_id: str, todo_id: str) -> None:
    todo = await _get_my_todo(db, user_id, todo_id)
    await repo.delete_todo(db, todo)
    await db.commit()
