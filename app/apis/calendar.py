"""캘린더 창구 (일기·사진·건강 할 일). API 명세서에 없는 화면 기능이라 새로 정의함."""
from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.calendar import (
    CalendarDayResult,
    CalendarMonthDay,
    EntryUpsertRequest,
    TodoCreateRequest,
    TodoResult,
    TodoUpdateRequest,
)
from app.schemas.common import DataResponse
from app.services import calendar_service

router = APIRouter(tags=["calendar"])


@router.get("/calendar/days", response_model=DataResponse[list[CalendarMonthDay]])
async def list_days(
    month: str = Query(..., description="예: 2026-10"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    """그 달에 일기·사진·건강 할 일이 있는 날들. 사진은 has_photo만 (용량 때문)."""
    return DataResponse(data=await calendar_service.list_month(db, user_id, month))


@router.get("/calendar/entries/{entry_date}", response_model=DataResponse[CalendarDayResult])
async def get_day(
    entry_date: date,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    """그날 하루치 (사진 포함)."""
    return DataResponse(data=await calendar_service.get_day(db, user_id, entry_date))


@router.put("/calendar/entries/{entry_date}", response_model=DataResponse[CalendarDayResult])
async def save_entry(
    entry_date: date,
    req: EntryUpsertRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    """일기·사진 저장 (보낸 필드만 바뀜, photo=null이면 사진 삭제)."""
    fields = {k: getattr(req, k) for k in req.model_fields_set}
    return DataResponse(data=await calendar_service.save_entry(db, user_id, entry_date, fields))


@router.post(
    "/calendar/days/{todo_date}/todos",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[TodoResult],
)
async def add_todo(
    todo_date: date,
    req: TodoCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await calendar_service.add_todo(db, user_id, todo_date, req.text))


@router.patch("/calendar/todos/{todo_id}", response_model=DataResponse[TodoResult])
async def update_todo(
    todo_id: str,
    req: TodoUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    fields = {k: getattr(req, k) for k in req.model_fields_set}
    return DataResponse(data=await calendar_service.update_todo(db, user_id, todo_id, fields))


@router.delete("/calendar/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(
    todo_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    await calendar_service.remove_todo(db, user_id, todo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
