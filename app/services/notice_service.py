"""서비스 안 공지: 이용자에게 보이는 목록과 관리자의 작성·수정. 관리자가 쓰거나 고치면 관리자 행위 기록에 남긴다."""
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.notice import Notice
from app.schemas.notice import NoticeAdmin, NoticeCreate, NoticePatch, NoticePublic
from app.services import audit_service

PUBLIC_LIMIT = 10   # 한꺼번에 보여 주는 게시 중 공지 수


def _status(n: Notice, now: datetime) -> str:
    if n.starts_at > now:
        return "upcoming"
    if n.ends_at is not None and n.ends_at <= now:
        return "ended"
    return "active"


def _admin(n: Notice, now: datetime) -> NoticeAdmin:
    return NoticeAdmin(notice_id=n.notice_id, title=n.title, body=n.body, starts_at=n.starts_at, ends_at=n.ends_at,
                       status=_status(n, now), created_by=n.created_by, created_at=n.created_at, updated_at=n.updated_at)


async def list_active(db: AsyncSession) -> list[NoticePublic]:
    now = utcnow()
    rows = (await db.execute(
        select(Notice).where(Notice.starts_at <= now, or_(Notice.ends_at.is_(None), Notice.ends_at > now))
        .order_by(Notice.starts_at.desc(), Notice.notice_id).limit(PUBLIC_LIMIT)
    )).scalars().all()
    return [NoticePublic(notice_id=n.notice_id, title=n.title, body=n.body, starts_at=n.starts_at, ends_at=n.ends_at) for n in rows]


async def admin_list(db: AsyncSession, limit: int, offset: int) -> list[NoticeAdmin]:
    now = utcnow()
    rows = (await db.execute(
        select(Notice).order_by(Notice.starts_at.desc(), Notice.notice_id).limit(limit).offset(offset)
    )).scalars().all()
    return [_admin(n, now) for n in rows]


async def create(db: AsyncSession, admin: str, req: NoticeCreate) -> NoticeAdmin:
    now = utcnow()
    starts_at = req.starts_at or now
    if req.ends_at is not None and req.ends_at <= starts_at:
        raise AppError(422, "NOTICE_RANGE_INVALID", "끝나는 시각은 시작하는 시각보다 뒤여야 합니다.")
    notice = Notice(title=req.title, body=req.body, starts_at=starts_at, ends_at=req.ends_at, created_by=admin, created_at=now)
    db.add(notice)
    await db.flush()
    await audit_service.record(db, admin, "notice_create", notice.notice_id[-8:], f"제목: {req.title[:40]}")
    await db.commit()
    return _admin(notice, now)


async def update(db: AsyncSession, admin: str, notice_id: str, req: NoticePatch) -> NoticeAdmin:
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise AppError(404, "NOTICE_NOT_FOUND", "공지를 찾을 수 없습니다.")
    now = utcnow()
    changes = []
    if req.title is not None and req.title != notice.title:
        notice.title = req.title
        changes.append("제목")
    if req.body is not None and req.body != notice.body:
        notice.body = req.body
        changes.append("내용")
    if req.starts_at is not None and req.starts_at != notice.starts_at:
        notice.starts_at = req.starts_at
        changes.append("시작")
    if req.end_now:
        notice.ends_at = now
        changes.append("지금 내림")
    elif req.ends_at is not None and req.ends_at != notice.ends_at:
        notice.ends_at = req.ends_at
        changes.append("종료")
    if notice.ends_at is not None and notice.ends_at <= notice.starts_at and not req.end_now:
        await db.rollback()
        raise AppError(422, "NOTICE_RANGE_INVALID", "끝나는 시각은 시작하는 시각보다 뒤여야 합니다.")
    if changes:
        notice.updated_at = now
        await audit_service.record(db, admin, "notice_update", notice.notice_id[-8:], "바꾼 것: " + ", ".join(changes))
    await db.commit()
    return _admin(notice, now)
