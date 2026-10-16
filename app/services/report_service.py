"""신고 처리 (관리자). 신고는 글·댓글 단위로 묶어서 보여 주고, 처리하면 같은 대상의 신고에 한꺼번에 결과가 붙는다.

관리자 행위 기록에는 대상의 번호 끝 8자만 남기고 글·댓글 내용은 담지 않는다. 신고된 글·댓글의 본문 미리보기는 처리를 위해
관리자 화면에만 내려가고, 목록을 연 것은 기록에 남는다 (같은 화면을 새로고침해도 10분 안에는 한 번만).
"""
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.community import CommunityComment, CommunityPost, CommunityPostPhoto, CommunityProfile, CommunityReport
from app.schemas.community import (
    AdminPostActionResult, AdminPostItem, AdminPostList, AdminReportItem, AdminReportList, ReportActionResult,
)
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
        text, author_id, target_status = post.body, post.user_id, post.status
        title, category = post.title, post.category
    else:
        c = await db.get(CommunityComment, target_id)
        post = await db.get(CommunityPost, c.post_id) if c is not None else None
        if c is None or post is None:
            return None
        text, author_id, target_status = c.body, c.user_id, c.status
        title, category = post.title, post.category
    nick = (await db.execute(select(CommunityProfile.nickname).where(CommunityProfile.user_id == author_id))).scalar_one_or_none()
    reasons: dict[str, int] = {}
    for r in rs:
        reasons[r.reason] = reasons.get(r.reason, 0) + 1
    handled = [r for r in rs if r.action is not None]
    last_action = max(handled, key=lambda r: r.handled_at).action if handled else None
    return AdminReportItem(
        target_type=kind, target_id=target_id, title=title, author_nickname=nick or "알 수 없음", author_user_id=author_id, category=category,
        report_count=len(rs), pending_count=pending, reasons=reasons, preview=text[:PREVIEW_LEN], status=state,
        action=last_action, last_reported_at=max(r.created_at for r in rs),
        auto_hidden=state == "pending" and target_status == "hidden",
    )


async def _apply(db: AsyncSession, target_type: str, target_id: str, obj, action: str) -> None:
    """글·댓글 상태 바꾸기. 신고 처리와 관리자 직접 관리(신고 없이)가 같이 쓴다.
    hide: 숨김 / delete: 내용 비우고 삭제 표시(행은 남김) / dismiss·restore: 숨김이면 다시 보이게."""
    if action == "hide":
        obj.status = "hidden"
    elif action == "delete":
        obj.status = "deleted"            # 내용은 비운다 (글은 제목도 가린다). 처리 기록을 보이기 위해 행은 남긴다
        if target_type == "post":
            obj.title, obj.body = DELETED_TITLE, ""
            await db.execute(delete(CommunityPostPhoto).where(CommunityPostPhoto.post_id == target_id))   # 사진도 지운다
        else:
            obj.body = ""
    elif action in ("dismiss", "restore") and obj.status == "hidden":
        obj.status = "visible"


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

    await _apply(db, target_type, target_id, obj, action)

    now = utcnow()
    for r in reports:
        r.action, r.handled_by, r.handled_at = action, admin, now
    await audit_service.record(db, admin, f"community_report_{action}", target=f"{target_type[0]}-{target_id[-8:]}")
    await db.commit()
    return ReportActionResult(target_type=target_type, target_id=target_id, action=action, handled=len(reports))

# ---------------------------------------------------------------- 관리자 글 관리 (신고 없이)
def _like(q: str) -> str:
    """검색어의 %·_를 글자 그대로 찾게 바꾼다."""
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def admin_posts(
    db: AsyncSession, admin: str, q: str | None, status: str | None, limit: int, offset: int,
) -> AdminPostList:
    """전체 커뮤니티 글 (최신순, 파티 글 제외). 목록을 연 것은 관리자 기록에 남긴다 (10분 안에는 한 번만)."""
    query = select(CommunityPost).where(CommunityPost.party_id.is_(None))
    if status:
        query = query.where(CommunityPost.status == status)
    if q and q.strip():
        pattern = _like(q.strip())
        query = query.where(CommunityPost.title.like(pattern, escape="\\") | CommunityPost.body.like(pattern, escape="\\"))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    posts = (await db.execute(
        query.order_by(CommunityPost.created_at.desc(), CommunityPost.post_id.desc()).limit(limit).offset(offset)
    )).scalars().all()

    ids = [p.user_id for p in posts]
    nicks = dict((await db.execute(
        select(CommunityProfile.user_id, CommunityProfile.nickname).where(CommunityProfile.user_id.in_(ids))
    )).all()) if ids else {}
    keys = [f"post:{p.post_id}" for p in posts]
    pending = dict((await db.execute(
        select(CommunityReport.target_key, func.count())
        .where(CommunityReport.target_key.in_(keys), CommunityReport.action.is_(None))
        .group_by(CommunityReport.target_key)
    )).all()) if keys else {}

    items = [AdminPostItem(
        post_id=p.post_id, title=p.title, preview=p.body[:PREVIEW_LEN], category=p.category,
        author_nickname=nicks.get(p.user_id, "알 수 없음"), author_user_id=p.user_id, status=p.status,
        pending_reports=pending.get(f"post:{p.post_id}", 0), created_at=p.created_at,
    ) for p in posts]
    await audit_service.record(db, admin, "community_posts_view", dedupe_seconds=audit_service.VIEW_DEDUPE_SECONDS)
    await db.commit()
    return AdminPostList(total=total, items=items)


async def moderate_post(db: AsyncSession, admin: str, post_id: str, action: str) -> AdminPostActionResult:
    """신고 없이 글 숨김 / 삭제 / 다시 보이기. 신고 처리와 같은 상태 변경(_apply)을 쓰고,
    그 글에 대기 중인 신고가 있으면 같은 결과로 함께 처리한다 (다시 보이기는 '문제 없음'으로)."""
    post = await db.get(CommunityPost, post_id)
    if post is None or post.party_id is not None:          # 파티 글은 관리 대상이 아니다 (파티원에게만 보이는 글)
        raise AppError(404, "COMMUNITY_NOT_FOUND", "글을 찾을 수 없어요.")
    if post.status == "deleted":
        raise AppError(409, "COMMUNITY_ALREADY_DELETED", "이미 삭제한 글이에요.")
    if (action, post.status) in (("hide", "hidden"), ("restore", "visible")):
        return AdminPostActionResult(post_id=post_id, status=post.status, handled_reports=0)   # 바뀔 게 없음

    await _apply(db, "post", post_id, post, action)
    reports = (await db.execute(select(CommunityReport).where(
        CommunityReport.target_key == f"post:{post_id}", CommunityReport.action.is_(None)))).scalars().all()
    now = utcnow()
    for r in reports:
        r.action, r.handled_by, r.handled_at = ("dismiss" if action == "restore" else action), admin, now
    await audit_service.record(db, admin, f"community_post_{action}", target=f"p-{post_id[-8:]}")
    await db.commit()
    return AdminPostActionResult(post_id=post_id, status=post.status, handled_reports=len(reports))