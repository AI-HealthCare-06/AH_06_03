"""비회원 문의. 스팸을 막기 위해 IP별 횟수 제한, 숨은 칸(허니팟), 링크 수 제한, 전체 대기 상한을 둔다.
관리자 행위 기록에는 문의 번호의 끝 8자만 남기고 내용은 담지 않는다."""
import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import utcnow
from app.models.guest_inquiry import GuestInquiry
from app.schemas.inquiry import (
    AdminGuestDetail, AdminGuestItem, AdminGuestList, GuestInquiryCreate, GuestInquiryView,
)
from app.services import audit_service

RETENTION_DAYS = 30        # 접수 후 30일이 지나면 삭제
PER_HOUR, PER_DAY = 3, 10  # IP별 접수 횟수 제한
MAX_OPEN = 300             # 답을 기다리는 비회원 문의가 이만큼 쌓이면 접수를 잠시 멈춘다
MAX_LINKS = 2


def _hash(value: str) -> str:
    """원문 대신 해시만 저장한다 (서버 비밀값으로 섞어서, 해시만으로는 IP나 번호를 되짚을 수 없다)."""
    return hmac.new(settings.JWT_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


def _new_code() -> str:
    raw = secrets.token_hex(6).upper()                   # 12자리
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def _norm(code: str) -> str:
    return code.replace("-", "").replace(" ", "").upper()


def _not_found() -> AppError:
    return AppError(404, "GUEST_INQUIRY_NOT_FOUND", "조회 번호를 찾을 수 없어요. 번호를 다시 확인해 주세요.")


async def create(db: AsyncSession, ip: str | None, req: GuestInquiryCreate) -> str:
    now = utcnow()
    await db.execute(delete(GuestInquiry).where(GuestInquiry.created_at < now - timedelta(days=RETENTION_DAYS)))
    code = _new_code()
    if req.website:                                      # 숨은 칸이 채워졌다 = 봇. 저장하지 않고 성공한 것처럼 보인다
        await db.commit()
        return code
    text = f"{req.title} {req.body}".lower()
    if text.count("http") > MAX_LINKS:
        raise AppError(422, "GUEST_INQUIRY_REJECTED", "링크가 많은 문의는 받을 수 없어요.")
    ip_hash = _hash(ip or "unknown")

    async def count_since(delta: timedelta) -> int:
        return (await db.execute(select(func.count()).select_from(GuestInquiry).where(
            GuestInquiry.ip_hash == ip_hash, GuestInquiry.created_at > now - delta))).scalar_one()

    if await count_since(timedelta(hours=1)) >= PER_HOUR or await count_since(timedelta(days=1)) >= PER_DAY:
        raise AppError(429, "GUEST_INQUIRY_RATE_LIMIT", "문의를 너무 자주 보냈어요. 잠시 뒤에 다시 보내 주세요.")
    open_count = (await db.execute(select(func.count()).select_from(GuestInquiry).where(GuestInquiry.answered_at.is_(None)))).scalar_one()
    if open_count >= MAX_OPEN:
        raise AppError(429, "GUEST_INQUIRY_BUSY", "지금은 문의가 많아 접수를 잠시 멈췄어요. 나중에 다시 시도해 주세요.")
    db.add(GuestInquiry(code_hash=_hash(_norm(code)), ip_hash=ip_hash, title=req.title, body=req.body, created_at=now))
    await db.commit()
    return code


async def view(db: AsyncSession, code: str) -> GuestInquiryView:
    inq = (await db.execute(select(GuestInquiry).where(GuestInquiry.code_hash == _hash(_norm(code))))).scalar_one_or_none()
    if inq is None:
        raise _not_found()
    return GuestInquiryView(title=inq.title, body=inq.body, created_at=inq.created_at, answer=inq.answer, answered_at=inq.answered_at)


# ---------------------------------------------------------------- 관리자
async def admin_list(db: AsyncSession, admin: str, status: str | None, limit: int, offset: int) -> AdminGuestList:
    q = select(GuestInquiry)
    if status == "open":
        q = q.where(GuestInquiry.answered_at.is_(None))
    elif status == "answered":
        q = q.where(GuestInquiry.answered_at.is_not(None))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await db.execute(q.order_by(GuestInquiry.created_at.desc()).limit(limit).offset(offset))).scalars().all()
    await audit_service.record(db, admin, "guest_inquiries_view", dedupe_seconds=audit_service.VIEW_DEDUPE_SECONDS)
    await db.commit()
    return AdminGuestList(total=int(total), items=[
        AdminGuestItem(inquiry_id=r.guest_inquiry_id, title=r.title, created_at=r.created_at, answered=r.answered_at is not None)
        for r in rows])


def _detail(i: GuestInquiry) -> AdminGuestDetail:
    return AdminGuestDetail(inquiry_id=i.guest_inquiry_id, title=i.title, body=i.body, created_at=i.created_at,
                            answer=i.answer, answered_by=i.answered_by, answered_at=i.answered_at)


async def admin_detail(db: AsyncSession, admin: str, inquiry_id: str) -> AdminGuestDetail:
    inq = await db.get(GuestInquiry, inquiry_id)
    if inq is None:
        raise _not_found()
    await audit_service.record(db, admin, "guest_inquiry_view", target=inq.guest_inquiry_id[-8:])
    await db.commit()
    return _detail(inq)


async def admin_answer(db: AsyncSession, admin: str, inquiry_id: str, answer: str) -> AdminGuestDetail:
    inq = await db.get(GuestInquiry, inquiry_id)
    if inq is None:
        raise _not_found()
    inq.answer, inq.answered_by, inq.answered_at = answer, admin, utcnow()
    await audit_service.record(db, admin, "guest_inquiry_answer", target=inq.guest_inquiry_id[-8:])
    await db.commit()
    return _detail(inq)
