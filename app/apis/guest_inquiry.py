"""비회원 문의 (로그인 없이). 로그인·가입이 안 될 때 쓴다."""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.databases import async_get_db
from app.schemas.common import DataResponse
from app.schemas.inquiry import GuestInquiryCreate, GuestInquiryCreated, GuestInquiryView
from app.services import access_log_service, guest_inquiry_service

router = APIRouter(tags=["guest-inquiries"])


@router.post("/guest-inquiries", status_code=status.HTTP_201_CREATED, response_model=DataResponse[GuestInquiryCreated])
async def create_guest_inquiry(request: Request, req: GuestInquiryCreate, db: AsyncSession = Depends(async_get_db)):
    code = await guest_inquiry_service.create(db, access_log_service.client_ip(request), req)
    return DataResponse(data=GuestInquiryCreated(code=code))


@router.get("/guest-inquiries/{code}", response_model=DataResponse[GuestInquiryView])
async def view_guest_inquiry(code: str, db: AsyncSession = Depends(async_get_db)):
    return DataResponse(data=await guest_inquiry_service.view(db, code))
