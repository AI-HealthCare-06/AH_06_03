"""커뮤니티 (이용자). 건강정보 동의와 상관없이 로그인한 회원이면 쓸 수 있다. 닉네임을 정해야 글·댓글·좋아요를 쓸 수 있다."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.community import (
    AttachOption, CommentCreate, CommentItem, LikeResult, MyCommunity, NicknameRequest, PostCreate, PostCreated, PostDetail, PostList,
    ReportRequest, ReportResult,
)
from app.services import community_service

router = APIRouter(prefix="/community", tags=["community"])


@router.get("/me", response_model=DataResponse[MyCommunity])
async def my_community(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await community_service.get_me(db, user_id))


@router.put("/me", response_model=DataResponse[MyCommunity])
async def set_nickname(req: NicknameRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await community_service.set_nickname(db, user_id, req.nickname))


@router.get("/attachable", response_model=DataResponse[list[AttachOption]])
async def attachable(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    """글쓰기에서 붙일 수 있는 "오늘 인증한 챌린지" (내 4주 챌린지 미션, 참여 중인 공통 챌린지)."""
    return DataResponse(data=await community_service.attach_options(db, user_id))


@router.get("/posts", response_model=DataResponse[PostList])
async def list_posts(
    category: Literal["diet", "exercise", "challenge", "tips"] | None = None,
    sort: Literal["latest", "popular"] = "latest", q: str | None = Query(None, max_length=50),
    limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await community_service.list_posts(db, user_id, category, sort, q, limit, offset))


@router.post("/posts", status_code=status.HTTP_201_CREATED, response_model=DataResponse[PostCreated])
async def create_post(req: PostCreate, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await community_service.create_post(db, user_id, req))


@router.get("/posts/{post_id}", response_model=DataResponse[PostDetail])
async def get_post(post_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await community_service.get_post(db, user_id, post_id))


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(post_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    await community_service.delete_post(db, user_id, post_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/posts/{post_id}/like", response_model=DataResponse[LikeResult])
async def like_post(post_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await community_service.toggle_like(db, user_id, post_id))


@router.get("/posts/{post_id}/comments", response_model=DataResponse[list[CommentItem]])
async def list_comments(post_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await community_service.list_comments(db, user_id, post_id))


@router.post("/posts/{post_id}/comments", status_code=status.HTTP_201_CREATED, response_model=DataResponse[CommentItem])
async def create_comment(
    post_id: str, req: CommentCreate, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)
):
    return DataResponse(data=await community_service.create_comment(db, user_id, post_id, req))


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    await community_service.delete_comment(db, user_id, comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/posts/{post_id}/report", status_code=status.HTTP_201_CREATED, response_model=DataResponse[ReportResult])
async def report_post(
    post_id: str, req: ReportRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)
):
    return DataResponse(data=await community_service.report_post(db, user_id, post_id, req))


@router.post("/comments/{comment_id}/report", status_code=status.HTTP_201_CREATED, response_model=DataResponse[ReportResult])
async def report_comment(
    comment_id: str, req: ReportRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)
):
    return DataResponse(data=await community_service.report_comment(db, user_id, comment_id, req))
