"""신고 처리 (관리자). 신고는 글·댓글 단위로 묶어서 보여 주고, 처리하면 같은 대상의 신고에 한꺼번에 결과가 붙는다.

관리자 행위 기록에는 대상의 번호 끝 8자만 남기고 글·댓글 내용은 담지 않는다. 신고된 글·댓글의 본문 미리보기는 처리를 위해
관리자 화면에만 내려가고, 목록을 연 것은 기록에 남는다 (같은 화면을 새로고침해도 10분 안에는 한 번만).
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.community import CommunityComment, CommunityPost, CommunityProfile, CommunityReport
from app.schemas.community import AdminReportItem, AdminReportList, ReportActionResult
from app.services import audit_service, community_service

PREVIEW_LEN = 200
DELETED_TITLE = "(삭제됨)"


async def admin_list(db: AsyncSession, admin: str, status: str | None, limit: int, offset: int) -> AdminReportList:
    reports = (await db.execute(select(CommunityReport).order_by(CommunityReport.created_at.desc()))).scalars().all()
    groups: dict[str, list[CommunityReport]] = {}
    for r in reports:
        groups.setdefault(r.target_key, []).append(r)

    items: list[AdminReportItem] = []
    for key, rs in groups.items():
        pending = [r for r in rs if r.action is None]
        state = "pending" if pending else "done"
        if status in ("pending", "done") and state != status:
            continue
        item = await _item(db, key, rs, len(pending), state)
        if item is not None:
            items.append(item)
    pending_total = sum(1 for rs in groups.values() if any(r.action is None for r in rs))
    items.sort(key=lambda i: i.last_reported_at, reverse=True)
    await audit_service.record(db, admin, "community_reports_view", dedupe_seconds=audit_service.VIEW_DEDUPE_SECONDS)
    await db.commit()
    return AdminReportList(total=len(items), pending_total=pending_total, items=items[offset:offset + limit])


async def _item(db: AsyncSession, key: str, rs: list[CommunityReport], pending: int, state: str) -> AdminReportItem | None:
    kind, _, target_id = key.partition(":")
    if kind == "post":
        post = await db.get(CommunityPost, target_id)
        if post is None:
            return None
        text, author_id = post.body, post.user_id
        title, category = post.title, post.category
    else:
        c = await db.get(CommunityComment, target_id)
        post = await db.get(CommunityPost, c.post_id) if c is not None else None
        if c is None or post is None:
            return None
        text, author_id = c.body, c.user_id
        title, category = post.title, post.category
    nick = (await db.execute(select(CommunityProfile.nickname).where(CommunityProfile.user_id == author_id))).scalar_one_or_none()
    reasons: dict[str, int] = {}
    for r in rs:
        reasons[r.reason] = reasons.get(r.reason, 0) + 1
    handled = [r for r in rs if r.action is not None]
    last_action = max(handled, key=lambda r: r.handled_at).action if handled else None
    return AdminReportItem(
        target_type=kind, target_id=target_id, title=title, author_nickname=nick or "알 수 없음", category=category,
        report_count=len(rs), pending_count=pending, reasons=reasons, preview=text[:PREVIEW_LEN], status=state,
        action=last_action, last_reported_at=max(r.created_at for r in rs),
    )


async def act(db: AsyncSession, admin: str, target_type: str, target_id: str, action: str) -> ReportActionResult:
    if target_type not in ("post", "comment"):
        raise AppError(404, "COMMUNITY_NOT_FOUND", "대상을 찾을 수 없어요.")
    key = f"{target_type}:{target_id}"
    reports = (await db.execute(select(CommunityReport).where(
        CommunityReport.target_key == key, CommunityReport.action.is_(None)))).scalars().all()
    obj = await db.get(CommunityPost if target_type == "post" else CommunityComment, target_id)
    if obj is None:
        raise AppError(404, "COMMUNITY_NOT_FOUND", "대상을 찾을 수 없어요.")
    if not reports:
        raise AppError(409, "REPORT_ALREADY_HANDLED", "이미 처리한 신고예요.")

    if action == "hide":
        obj.status = "hidden"
    elif action == "delete":
        obj.status = "deleted"            # 내용은 비운다 (글은 제목도 가린다). 처리 기록을 보이기 위해 행은 남긴다
        if target_type == "post":
            obj.title, obj.body = DELETED_TITLE, ""
        else:
            obj.body = ""
    now = utcnow()
    for r in reports:
        r.action, r.handled_by, r.handled_at = action, admin, now
    await audit_service.record(db, admin, f"community_report_{action}", target=f"{target_type[0]}-{target_id[-8:]}")
    await db.commit()
    return ReportActionResult(target_type=target_type, target_id=target_id, action=action, handled=len(reports))
