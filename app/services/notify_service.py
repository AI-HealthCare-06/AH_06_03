"""이벤트 알림(댓글·대댓글·문의 답변·파티 참여)을 누구에게 어떤 문구로 보낼지 정한다. 실제 발송은 push_service.send.
원래 요청(댓글 저장 등)이 commit된 뒤에 부른다. 발송이 실패해도 원래 요청은 성공으로 둔다(push_service.send가 오류를 삼킨다).
본인이 한 일은 본인에게 보내지 않는다. 알림에는 댓글·문의 내용을 넣지 않는다(잠금 화면 노출 방지)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import CommunityProfile
from app.services import push_service


async def _nickname(db: AsyncSession, user_id: str) -> str:
    """닉네임, 없으면 '누군가'."""
    name = (await db.execute(
        select(CommunityProfile.nickname).where(CommunityProfile.user_id == user_id)
    )).scalar_one_or_none()
    return name or "누군가"


async def comment_added(db: AsyncSession, post_id: str, post_author_id: str, commenter_id: str) -> None:
    """내 글에 댓글이 달렸을 때 → 글쓴이에게."""
    if post_author_id == commenter_id:
        return
    name = await _nickname(db, commenter_id)
    await push_service.send(db, post_author_id, "comment", "새 댓글이 달렸어요 💬",
                            f"{name}님이 내 글에 댓글을 남겼어요.", f"post.html?id={post_id}")


async def reply_added(db: AsyncSession, post_id: str, comment_id: str, parent_author_id: str, replier_id: str) -> None:
    """내 댓글에 답글이 달렸을 때 → 원 댓글 쓴 사람에게만 (글쓴이에게는 가지 않는다)."""
    if parent_author_id == replier_id:
        return
    name = await _nickname(db, replier_id)
    await push_service.send(db, parent_author_id, "comment", "내 댓글에 답글이 달렸어요 💬",
                            f"{name}님이 내 댓글에 답글을 남겼어요.", f"post.html?id={post_id}#c-{comment_id}")


async def inquiry_answered(db: AsyncSession, asker_id: str) -> None:
    """문의에 답변이 왔을 때 → 문의한 사람에게."""
    await push_service.send(db, asker_id, "inquiry", "문의에 답변이 도착했어요 💌",
                            "남겨 주신 문의에 답변을 드렸어요. 확인해 주세요.", "inquiries.html")


async def party_joined(db: AsyncSession, member_ids: list[str], joiner_id: str) -> None:
    """파티에 새 멤버가 들어왔을 때 → 이미 있던 멤버 모두에게 (새로 들어온 본인은 제외)."""
    name = await _nickname(db, joiner_id)
    for uid in member_ids:
        if uid != joiner_id:
            await push_service.send(db, uid, "party", "파티에 새 친구가 왔어요 🎉",
                                    f"{name}님이 우리 파티에 참여했어요.", "party-home.html")