"""1:1 문의 (이용자). 건강정보 동의와 상관없이 로그인한 회원이면 쓸 수 있다."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.inquiry import InquiryCreate, InquiryDetail, InquiryItem, InquiryList
from app.services import inquiry_service

router = APIRouter(tags=["inquiries"])


@router.post("/inquiries", status_code=status.HTTP_201_CREATED, response_model=DataResponse[InquiryItem])
async def create_inquiry(req: InquiryCreate, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await inquiry_service.create(db, user_id, req))


@router.get("/inquiries", response_model=DataResponse[InquiryList])
async def my_inquiries(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await inquiry_service.list_mine(db, user_id))


@router.get("/inquiries/{inquiry_id}", response_model=DataResponse[InquiryDetail])
async def my_inquiry(inquiry_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await inquiry_service.get_mine(db, user_id, inquiry_id))
