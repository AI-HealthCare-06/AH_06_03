"""대상 확인 답 저장·조회 창구 (API 명세서에 없는 화면 값이라 새로 정의함)."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.core.errors import AppError
from app.core.security import utcnow
from app.models.eligibility import UserEligibility
from app.schemas.common import DataResponse

router = APIRouter(tags=["eligibility"])


class EligibilityBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age_band: Literal["in", "bOnly", "under19"]
    chd: bool
    emergency: Literal["no", "yes", "unsure"] = "no"


@router.get("/users/me/eligibility", response_model=DataResponse[EligibilityBody])
async def get_eligibility(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    row = await db.get(UserEligibility, user_id)
    if row is None:
        raise AppError(404, "ELIGIBILITY_NOT_FOUND", "대상 확인 기록이 없습니다.")
    return DataResponse(data=EligibilityBody(age_band=row.age_band, chd=row.chd, emergency=row.emergency))


@router.put("/users/me/eligibility", response_model=DataResponse[EligibilityBody])
async def save_eligibility(
    req: EligibilityBody, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)
):
    """대상 확인 답을 저장한다 (다시 확인하면 덮어쓴다)."""
    row = await db.get(UserEligibility, user_id)
    if row is None:
        row = UserEligibility(user_id=user_id, age_band=req.age_band, chd=req.chd, emergency=req.emergency, updated_at=utcnow())
        db.add(row)
    else:
        row.age_band, row.chd, row.emergency, row.updated_at = req.age_band, req.chd, req.emergency, utcnow()
    await db.commit()
    return DataResponse(data=req)
