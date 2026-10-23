"""커뮤니티: 닉네임, 글, 댓글, 좋아요, 신고(이용자 쪽).

- 닉네임을 정해야 글·댓글을 쓸 수 있다. 처음 정할 때 파이 시작 선물 10개.
- 글쓰기는 하루 3번까지 파이 2개를 받는다 (한국 날짜 기준).
- 운영팀이 숨긴 글은 작성자에게만 안내와 함께 보이고, 다른 사람의 목록·상세에는 나오지 않는다.
- 글·댓글은 건강정보를 적지 않는 곳이라, 신고(건강정보 포함 사유)로 운영팀이 숨긴다.
"""
from datetime import timedelta

from sqlalchemy import and_, delete, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import AppError
from app.core.security import utcnow
from app.models.community import (
    CommunityComment, CommunityLike, CommunityPost, CommunityPostPhoto, CommunityProfile, CommunityReport,
)
from app.schemas.community import (
    AttachOption, CommentCreate, CommentItem, CommentUpdate, LikeResult, MyCommunity, PostAttach, PostCreate, PostCreated, PostDetail,
    PhotoResult, PostItem, PostList, ReportRequest, ReportResult,
)
from app.models.party import PartyMember
from app.services import admin_alert, audit_service, photo_check, pie_service, post_attach_service

WELCOME_PIE = 10
POST_PIE = 2
POST_PIE_PER_DAY = 3
HIDDEN_NOTICE = "운영 정책에 따라 숨김 처리됐어요"
AUTO_HIDE_REPORTERS = 3    # 서로 다른 사람이 이만큼 신고하면 관리자가 보기 전까지 자동으로 숨긴다 (한 사람이 혼자 내리지 못하게)
DAILY_REPORT_LIMIT = 10    # 한 사람이 24시간 동안 할 수 있는 신고 수 (아무 글이나 신고하고 다니는 것을 막는다)
AUTO_HIDE_ACTOR = "system(신고 누적)"   # 자동 숨김을 관리자 기록에 남길 때의 기록자 (관리자 목록 변경의 "system(서버 설정)"과 같은 방식)
PREVIEW_LEN = 100
POPULAR_DAYS = 30


# ---------------------------------------------------------------- 닉네임
async def get_me(db: AsyncSession, user_id: str) -> MyCommunity:
    p = await db.get(CommunityProfile, user_id)
    return MyCommunity(nickname=p.nickname if p else None)


async def set_nickname(db: AsyncSession, user_id: str, nickname: str) -> MyCommunity:
    taken = (await db.execute(select(CommunityProfile.user_id).where(
        CommunityProfile.nickname == nickname, CommunityProfile.user_id != user_id))).first()
    if taken is not None:
        raise AppError(409, "NICKNAME_TAKEN", "이미 쓰고 있는 닉네임이에요. 다른 닉네임을 적어 주세요.")
    p = await db.get(CommunityProfile, user_id)
    gift = 0
    if p is None:
        db.add(CommunityProfile(user_id=user_id, nickname=nickname, created_at=utcnow()))
        if await pie_service.add(db, user_id, WELCOME_PIE, pie_service.WELCOME, "welcome"):
            gift = WELCOME_PIE
    else:
        p.nickname = nickname
    try:
        await db.commit()
    except IntegrityError:          # 동시에 같은 닉네임을 정한 경우
        await db.rollback()
        raise AppError(409, "NICKNAME_TAKEN", "이미 쓰고 있는 닉네임이에요. 다른 닉네임을 적어 주세요.")
    return MyCommunity(nickname=nickname, pie_gift=gift)


async def require_nickname(db: AsyncSession, user_id: str) -> str:
    p = await db.get(CommunityProfile, user_id)
    if p is None:
        raise AppError(409, "NICKNAME_REQUIRED", "닉네임을 먼저 정해 주세요.")
    return p.nickname


def not_found(what: str = "글") -> AppError:
    return AppError(404, "COMMUNITY_NOT_FOUND", f"{what}을 찾을 수 없어요.")


# ---------------------------------------------------------------- 글
def _like_count():
    return (select(func.count()).select_from(CommunityLike)
            .where(CommunityLike.post_id == CommunityPost.post_id).correlate(CommunityPost).scalar_subquery())


def _comment_count():
    return (select(func.count()).select_from(CommunityComment)
            .where(CommunityComment.post_id == CommunityPost.post_id, CommunityComment.status == "visible")
            .correlate(CommunityPost).scalar_subquery())


def _photo_count():
    return (select(func.count()).select_from(CommunityPostPhoto)
            .where(CommunityPostPhoto.post_id == CommunityPost.post_id).correlate(CommunityPost).scalar_subquery())


def _liked_by(user_id: str):
    return exists().where(CommunityLike.post_id == CommunityPost.post_id, CommunityLike.user_id == user_id)


def _item(p: CommunityPost, nickname: str | None, likes: int, comments: int, liked: bool, me: str, photos: int = 0) -> dict:
    hidden = p.status == "hidden"
    return dict(
        post_id=p.post_id, category=p.category, title=p.title, preview="" if hidden else p.body[:PREVIEW_LEN],
        author_nickname=nickname or "알 수 없음", created_at=p.created_at, like_count=likes, comment_count=comments,
        liked_by_me=bool(liked), mine=p.user_id == me, hidden=hidden, notice=HIDDEN_NOTICE if hidden else None,
        attach=PostAttach(kind=p.attach_kind, label=p.attach_label, days=p.attach_days or 0) if p.attach_kind and not hidden else None,
        photo_count=0 if hidden else int(photos or 0),
    )


def _visible_to(user_id: str):
    """남에게는 visible만, 내 글은 숨김 처리된 것도 (삭제된 글은 아무에게도 안 보인다). 파티 글은 그 파티원에게만."""
    my_party = select(PartyMember.party_id).where(PartyMember.user_id == user_id).scalar_subquery()
    return and_(
        or_(CommunityPost.status == "visible", (CommunityPost.status == "hidden") & (CommunityPost.user_id == user_id)),
        or_(CommunityPost.party_id.is_(None), CommunityPost.party_id == my_party),
    )


def _reported_by(user_id: str, target):
    """내가 신고한 글·댓글인지. 신고하면 다른 사람에게는 그대로여도 나의 목록에서는 바로 빠진다
    (관리자가 '문제 없음'으로 처리해도 신고한 사람에게는 계속 안 보인다). 글 자체를 여는 것은 막지 않는다."""
    return exists(select(CommunityReport.report_id).where(CommunityReport.user_id == user_id, target))


async def _can_see_party(db: AsyncSession, user_id: str, p: CommunityPost) -> bool:
    """파티 글이 아니면 누구나, 파티 글이면 그 파티원만."""
    if p.party_id is None:
        return True
    return (await db.execute(select(PartyMember.party_member_id).where(
        PartyMember.user_id == user_id, PartyMember.party_id == p.party_id))).first() is not None


async def _load_post(db: AsyncSession, user_id: str, post_id: str):
    row = (await db.execute(
        select(CommunityPost, CommunityProfile.nickname, _like_count(), _comment_count(), _liked_by(user_id), _photo_count())
        .outerjoin(CommunityProfile, CommunityProfile.user_id == CommunityPost.user_id)
        .where(CommunityPost.post_id == post_id, _visible_to(user_id))
    )).first()
    if row is None:
        raise not_found()
    return row


async def attach_options(db: AsyncSession, user_id: str) -> list[AttachOption]:
    return await post_attach_service.options(db, user_id)


async def create_post(db: AsyncSession, user_id: str, req: PostCreate, party_id: str | None = None,
                      party_card: tuple[str, int] | None = None) -> PostCreated:
    nickname = await require_nickname(db, user_id)
    kind = label = days = None
    if party_card is not None:                     # 파티 글에 붙이는 "파티 연속 인증" 카드
        kind, (label, days) = "party", party_card
    elif req.attach is not None:
        kind, label, days = await post_attach_service.resolve(db, user_id, req.attach)
    post = CommunityPost(user_id=user_id, category=req.category, title=req.title, body=req.body,
                         status="visible", created_at=utcnow(), attach_kind=kind, attach_label=label, attach_days=days, party_id=party_id)
    db.add(post)
    await db.flush()
    gain = 0
    if party_id is None and await pie_service.count_today(db, user_id, pie_service.POST_WRITE) < POST_PIE_PER_DAY:   # 파티 글은 파이를 주지 않는다
        if await pie_service.add(db, user_id, POST_PIE, pie_service.POST_WRITE, post.post_id):
            gain = POST_PIE
    await db.commit()
    return PostCreated(**_item(post, nickname, 0, 0, False, user_id), body=post.body, pie_gain=gain)


async def list_posts(db: AsyncSession, user_id: str, category: str | None, sort: str, q: str | None,
                     limit: int, offset: int, party_id: str | None = None) -> PostList:
    base = select(CommunityPost).where(_visible_to(user_id), ~_reported_by(user_id, CommunityReport.post_id == CommunityPost.post_id))
    base = base.where(CommunityPost.party_id == party_id) if party_id else base.where(CommunityPost.party_id.is_(None))
    if category:
        base = base.where(CommunityPost.category == category)
    if sort == "popular":
        base = base.where(CommunityPost.created_at >= utcnow() - timedelta(days=POPULAR_DAYS))
    if q and q.strip():
        like = q.strip()
        base = base.where(or_(CommunityPost.title.contains(like, autoescape=True),
                              CommunityPost.body.contains(like, autoescape=True)))
    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    likes = _like_count()
    stmt = (select(CommunityPost, CommunityProfile.nickname, likes, _comment_count(), _liked_by(user_id), _photo_count())
            .outerjoin(CommunityProfile, CommunityProfile.user_id == CommunityPost.user_id)
            .where(CommunityPost.post_id.in_(select(base.subquery().c.post_id))))
    stmt = stmt.order_by(likes.desc(), CommunityPost.created_at.desc()) if sort == "popular" \
        else stmt.order_by(CommunityPost.created_at.desc(), CommunityPost.post_id)
    rows = (await db.execute(stmt.limit(limit).offset(offset))).all()
    return PostList(total=total, items=[PostItem(**_item(p, n, lk, cm, ld, user_id, ph)) for p, n, lk, cm, ld, ph in rows])


async def get_post(db: AsyncSession, user_id: str, post_id: str) -> PostDetail:
    p, n, lk, cm, ld, ph = await _load_post(db, user_id, post_id)
    return PostDetail(**_item(p, n, lk, cm, ld, user_id, ph), body="" if p.status == "hidden" else p.body)


async def _remove_post_rows(db: AsyncSession, post_id: str) -> None:
    """글에 딸린 좋아요·댓글·신고를 지운다 (DB의 CASCADE와 같은 결과, 테스트 DB에서도 같게 동작하도록 직접 지운다)."""
    comment_ids = select(CommunityComment.comment_id).where(CommunityComment.post_id == post_id)
    await db.execute(delete(CommunityReport).where(
        or_(CommunityReport.post_id == post_id, CommunityReport.comment_id.in_(comment_ids))))
    await db.execute(delete(CommunityLike).where(CommunityLike.post_id == post_id))
    await db.execute(delete(CommunityComment).where(CommunityComment.post_id == post_id))
    await db.execute(delete(CommunityPostPhoto).where(CommunityPostPhoto.post_id == post_id))


async def delete_post(db: AsyncSession, user_id: str, post_id: str) -> None:
    p = await db.get(CommunityPost, post_id)
    if p is None or p.user_id != user_id or p.status == "deleted":
        raise not_found()
    await _remove_post_rows(db, post_id)
    await db.delete(p)
    await db.commit()


async def toggle_like(db: AsyncSession, user_id: str, post_id: str) -> LikeResult:
    await require_nickname(db, user_id)
    p = await db.get(CommunityPost, post_id)
    if p is None or p.status != "visible" or not await _can_see_party(db, user_id, p):
        raise not_found()
    mine = (await db.execute(select(CommunityLike).where(
        CommunityLike.post_id == post_id, CommunityLike.user_id == user_id))).scalar_one_or_none()
    if mine is None:
        db.add(CommunityLike(post_id=post_id, user_id=user_id))
        liked = True
    else:
        await db.delete(mine)
        liked = False
    await db.commit()
    count = (await db.execute(select(func.count()).select_from(CommunityLike)
                              .where(CommunityLike.post_id == post_id))).scalar_one()
    return LikeResult(liked=liked, like_count=int(count))


# ---------------------------------------------------------------- 댓글
async def list_comments(db: AsyncSession, user_id: str, post_id: str) -> list[CommentItem]:
    await _load_post(db, user_id, post_id)
    reply = aliased(CommunityComment)
    has_reply = exists(select(reply.comment_id).where(reply.parent_id == CommunityComment.comment_id, reply.status == "visible"))
    rows = (await db.execute(
        select(CommunityComment, CommunityProfile.nickname)
        .outerjoin(CommunityProfile, CommunityProfile.user_id == CommunityComment.user_id)
        .where(CommunityComment.post_id == post_id,
               or_(CommunityComment.status == "visible", and_(CommunityComment.status == "deleted", has_reply)),
               ~_reported_by(user_id, CommunityReport.comment_id == CommunityComment.comment_id))
        .order_by(CommunityComment.created_at, CommunityComment.comment_id))).all()
    return [CommentItem(comment_id=c.comment_id, body="" if c.status == "deleted" else c.body,
                        author_nickname="" if c.status == "deleted" else (n or "알 수 없음"),
                        created_at=c.created_at, mine=c.status != "deleted" and c.user_id == user_id,
                        parent_id=c.parent_id, deleted=c.status == "deleted") for c, n in rows]


async def create_comment(db: AsyncSession, user_id: str, post_id: str, req: CommentCreate) -> CommentItem:
    nickname = await require_nickname(db, user_id)
    p = await db.get(CommunityPost, post_id)
    if p is None or p.status != "visible" or not await _can_see_party(db, user_id, p):
        raise not_found()
    parent_id = None
    if req.parent_id is not None:
        parent = await db.get(CommunityComment, req.parent_id)
        if parent is None or parent.post_id != post_id or parent.status != "visible":
            raise not_found("댓글")
        parent_id = parent.parent_id or parent.comment_id   # 대댓글에 단 답글은 원 댓글 아래로 붙인다(한 단계만)
    c = CommunityComment(post_id=post_id, user_id=user_id, parent_id=parent_id, body=req.body, status="visible", created_at=utcnow())
    db.add(c)
    await db.commit()
    return CommentItem(comment_id=c.comment_id, body=c.body, author_nickname=nickname, created_at=c.created_at, mine=True, parent_id=parent_id)


async def update_comment(db: AsyncSession, user_id: str, comment_id: str, req: CommentUpdate) -> CommentItem:
    """내 댓글 본문만 고친다 (지운 댓글·남의 댓글은 404)."""
    c = await db.get(CommunityComment, comment_id)
    if c is None or c.user_id != user_id or c.status != "visible":
        raise not_found("댓글")
    c.body = req.body
    await db.commit()
    nickname = await require_nickname(db, user_id)
    return CommentItem(comment_id=c.comment_id, body=c.body, author_nickname=nickname, created_at=c.created_at, mine=True, parent_id=c.parent_id)


async def delete_comment(db: AsyncSession, user_id: str, comment_id: str) -> None:
    c = await db.get(CommunityComment, comment_id)
    if c is None or c.user_id != user_id or c.status == "deleted":
        raise not_found("댓글")
    await db.execute(delete(CommunityReport).where(CommunityReport.comment_id == comment_id))
    has_reply = (await db.execute(select(CommunityComment.comment_id).where(
        CommunityComment.parent_id == comment_id, CommunityComment.status == "visible").limit(1))).first() is not None
    if has_reply:
        c.status = "deleted"   # 답글이 달린 댓글은 자리만 남긴다("삭제된 댓글이에요")
    else:
        await db.delete(c)
    await db.commit()


# ---------------------------------------------------------------- 신고
async def _report(db: AsyncSession, user_id: str, key: str, req: ReportRequest, obj, **target) -> ReportResult:
    dup = (await db.execute(select(CommunityReport.report_id).where(
        CommunityReport.user_id == user_id, CommunityReport.target_key == key))).first()
    if dup is not None:
        raise AppError(409, "ALREADY_REPORTED", "이미 신고한 글이에요.")
    now = utcnow()
    recent = (await db.execute(select(func.count()).select_from(CommunityReport).where(
        CommunityReport.user_id == user_id, CommunityReport.created_at > now - timedelta(hours=24)))).scalar_one()
    if recent >= DAILY_REPORT_LIMIT:
        raise AppError(429, "REPORT_DAILY_LIMIT", f"신고는 하루 {DAILY_REPORT_LIMIT}건까지 할 수 있어요. 내일 다시 시도해 주세요.")
    db.add(CommunityReport(user_id=user_id, target_key=key, reason=req.reason, created_at=now, **target))
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "ALREADY_REPORTED", "이미 신고한 글이에요.")
    # 처리 대기 중인 신고(한 사람당 한 건이라 곧 신고한 사람 수)가 기준에 닿으면 관리자 확인 전까지 숨긴다.
    # 관리자가 '문제 없음'으로 처리하면 다시 보인다 (report_service.act).
    pending = (await db.execute(select(func.count()).select_from(CommunityReport).where(
        CommunityReport.target_key == key, CommunityReport.action.is_(None)))).scalar_one()
    auto_hidden = pending >= AUTO_HIDE_REPORTERS and obj.status == "visible"
    if auto_hidden:
        obj.status = "hidden"
        # 누가(시스템) 언제 무엇을 숨겼는지 관리자 기록에 남긴다. 사람이 한 조치처럼 번호 끝 8자만, 내용은 남기지 않는다
        kind, _, target_id = key.partition(":")          # "post" 또는 "comment"
        await audit_service.record(db, AUTO_HIDE_ACTOR, "community_auto_hide",
                                   target=f"{kind[0]}-{target_id[-8:]}", detail=f"신고 {pending}명")
    await db.commit()
    if auto_hidden:   # 숨겨지는 순간에 한 번만. 내용·작성자·번호는 보내지 않는다
        what = "글" if key.startswith("post:") else "댓글"
        admin_alert.notify(f"🔒 커뮤니티 {what} 1건이 신고 {AUTO_HIDE_REPORTERS}명으로 자동 숨김됐어요. "
                           f"관리자 화면의 신고 탭에서 확인해 주세요.")
    return ReportResult()


async def report_post(db: AsyncSession, user_id: str, post_id: str, req: ReportRequest) -> ReportResult:
    p = await db.get(CommunityPost, post_id)
    if p is None or p.status != "visible" or not await _can_see_party(db, user_id, p):
        raise not_found()
    if p.user_id == user_id:
        raise AppError(400, "REPORT_OWN", "내 글은 신고할 수 없어요.")
    return await _report(db, user_id, f"post:{post_id}", req, p, post_id=post_id)


async def report_comment(db: AsyncSession, user_id: str, comment_id: str, req: ReportRequest) -> ReportResult:
    c = await db.get(CommunityComment, comment_id)
    if c is None or c.status != "visible":
        raise not_found("댓글")
    if c.user_id == user_id:
        raise AppError(400, "REPORT_OWN", "내 댓글은 신고할 수 없어요.")
    post = await db.get(CommunityPost, c.post_id)
    if post is None or post.status != "visible" or not await _can_see_party(db, user_id, post):
        raise not_found("댓글")
    return await _report(db, user_id, f"comment:{comment_id}", req, c, comment_id=comment_id)


# ---------------------------------------------------------------- 사진
async def add_photo(db: AsyncSession, user_id: str, post_id: str, data: bytes) -> PhotoResult:
    """내 글에 사진 한 장 올리기. JPEG만, 300KB 이하, 글당 3장, 촬영 위치 정보가 있으면 거절."""
    p = await db.get(CommunityPost, post_id)
    if p is None or p.user_id != user_id or p.status != "visible":
        raise not_found()
    if not photo_check.is_jpeg(data):
        raise AppError(415, "PHOTO_NOT_JPEG", "JPEG 사진만 올릴 수 있어요.")
    if len(data) > photo_check.MAX_BYTES:
        raise AppError(413, "PHOTO_TOO_LARGE", "사진은 한 장에 300KB 이하만 올릴 수 있어요.")
    if photo_check.has_location(data):
        raise AppError(400, "PHOTO_HAS_LOCATION", "촬영 위치가 담긴 사진은 올릴 수 없어요.")
    count = int((await db.execute(select(func.count()).select_from(CommunityPostPhoto)
                                  .where(CommunityPostPhoto.post_id == post_id))).scalar_one())
    if count >= photo_check.MAX_PHOTOS:
        raise AppError(409, "PHOTO_LIMIT", "사진은 한 글에 3장까지 올릴 수 있어요.")
    db.add(CommunityPostPhoto(post_id=post_id, position=count, data=data, created_at=utcnow()))
    try:
        await db.commit()
    except IntegrityError:                       # 같은 순간에 두 장이 같은 번호를 잡은 경우
        await db.rollback()
        raise AppError(409, "PHOTO_LIMIT", "사진을 다시 올려 주세요.")
    return PhotoResult(position=count)


async def get_photo(db: AsyncSession, user_id: str, post_id: str, position: int) -> bytes:
    """사진 한 장. 글을 볼 수 있는 사람만 받는다 (숨김 처리된 글은 작성자만, 파티 글은 파티원만)."""
    await _load_post(db, user_id, post_id)
    row = (await db.execute(select(CommunityPostPhoto.data).where(
        CommunityPostPhoto.post_id == post_id, CommunityPostPhoto.position == position))).first()
    if row is None:
        raise not_found("사진")
    return row[0]
