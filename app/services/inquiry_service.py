"""1:1 문의. 이용자는 문의를 남기고 답변을 보며, 관리자는 목록을 보고 답한다. 관리자 행위 기록에는 문의 번호만 남기고 내용은 담지 않는다."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.inquiry import Inquiry
from app.schemas.inquiry import (
    AdminInquiryDetail, AdminInquiryItem, AdminInquiryList, InquiryCreate, InquiryDetail, InquiryItem, InquiryList,
)
from app.services import admin_alert, audit_service,notify_service

MAX_OPEN = 5    # 답을 기다리는 문의는 한 사람당 5개까지 (도배 방지)


def _not_found() -> AppError:
    return AppError(404, "INQUIRY_NOT_FOUND", "문의를 찾을 수 없습니다.")


def _item(i: Inquiry) -> InquiryItem:
    return InquiryItem(inquiry_id=i.inquiry_id, title=i.title, created_at=i.created_at,
                       answered=i.answered_at is not None, unread=i.answered_at is not None and i.user_read_at is None)


async def create(db: AsyncSession, user_id: str, req: InquiryCreate) -> InquiryItem:
    open_count = (await db.execute(
        select(func.count()).select_from(Inquiry).where(Inquiry.user_id == user_id, Inquiry.answered_at.is_(None))
    )).scalar_one()
    if open_count >= MAX_OPEN:
        raise AppError(429, "INQUIRY_LIMIT", "답변을 기다리는 문의가 이미 있어요. 답변이 온 뒤에 새로 남겨 주세요.")
    inq = Inquiry(user_id=user_id, title=req.title, body=req.body, created_at=utcnow())
    db.add(inq)
    await db.commit()
    # 늦게 답하지 않게 관리자에게 알린다. 제목·내용·작성자는 보내지 않는다 (디스코드는 서비스 밖)
    admin_alert.notify("💬 새 1:1 문의가 1건 들어왔어요. 관리자 화면의 문의 탭에서 확인해 주세요.")
    return _item(inq)


async def list_mine(db: AsyncSession, user_id: str) -> InquiryList:
    rows = (await db.execute(
        select(Inquiry).where(Inquiry.user_id == user_id).order_by(Inquiry.created_at.desc())
    )).scalars().all()
    items = [_item(r) for r in rows]
    return InquiryList(unread=sum(1 for i in items if i.unread), items=items)


async def get_mine(db: AsyncSession, user_id: str, inquiry_id: str) -> InquiryDetail:
    inq = await db.get(Inquiry, inquiry_id)
    if inq is None or inq.user_id != user_id:
        raise _not_found()
    if inq.answered_at is not None and inq.user_read_at is None:
        inq.user_read_at = utcnow()           # 답변을 열어 보면 읽음 처리
        await db.commit()
    return InquiryDetail(inquiry_id=inq.inquiry_id, title=inq.title, body=inq.body, created_at=inq.created_at,
                         answer=inq.answer, answered_at=inq.answered_at)


# ---------------------------------------------------------------- 관리자
async def admin_list(db: AsyncSession, admin: str, status: str | None, limit: int, offset: int) -> AdminInquiryList:
    q = select(Inquiry)
    if status == "open":
        q = q.where(Inquiry.answered_at.is_(None))
    elif status == "answered":
        q = q.where(Inquiry.answered_at.is_not(None))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await db.execute(q.order_by(Inquiry.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    await audit_service.record(db, admin, "inquiries_view", dedupe_seconds=audit_service.VIEW_DEDUPE_SECONDS)
    await db.commit()
    return AdminInquiryList(total=int(total), items=[
        AdminInquiryItem(inquiry_id=r.inquiry_id, user_id_short=r.user_id[-8:], title=r.title,
                         created_at=r.created_at, answered=r.answered_at is not None) for r in rows])


def _admin_detail(i: Inquiry) -> AdminInquiryDetail:
    return AdminInquiryDetail(inquiry_id=i.inquiry_id, user_id_short=i.user_id[-8:], title=i.title, body=i.body,
                              created_at=i.created_at, answer=i.answer, answered_by=i.answered_by, answered_at=i.answered_at)


async def admin_detail(db: AsyncSession, admin: str, inquiry_id: str) -> AdminInquiryDetail:
    inq = await db.get(Inquiry, inquiry_id)
    if inq is None:
        raise _not_found()
    await audit_service.record(db, admin, "inquiry_view", target=inq.inquiry_id[-8:])
    await db.commit()
    return _admin_detail(inq)


async def admin_answer(db: AsyncSession, admin: str, inquiry_id: str, answer: str) -> AdminInquiryDetail:
    inq = await db.get(Inquiry, inquiry_id)
    if inq is None:
        raise _not_found()
    inq.answer, inq.answered_by, inq.answered_at = answer, admin, utcnow()
    inq.user_read_at = None                   # 답을 고치면 이용자에게 다시 새 답변으로 보인다
    await audit_service.record(db, admin, "inquiry_answer", target=inq.inquiry_id[-8:])
    await db.commit()
    await notify_service.inquiry_answered(db, inq.user_id)           # 문의한 사람에게 알림 (내용은 안 넣음)
    return _admin_detail(inq)


async def admin_delete(db: AsyncSession, admin: str, inquiry_id: str) -> None:
    """관리자가 문의 하나를 지운다 (이용자 목록에서도 사라진다)."""
    inq = await db.get(Inquiry, inquiry_id)
    if inq is None:
        raise _not_found()
    await db.delete(inq)
    await audit_service.record(db, admin, "inquiry_delete", target=inquiry_id[-8:])
    await db.commit()
