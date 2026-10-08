"""대상 확인(이용 적합성·응급 확인) 저장·조회 창구 (ERD v8 eligibility_assessments, REQ-ELIG-001~004).
API 명세서에는 없는 화면 값이라 새로 정의했다."""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.core.errors import AppError
from app.core.security import utcnow
from app.repositories import eligibility_repository
from app.schemas.common import DataResponse

router = APIRouter(tags=["eligibility"])


class EligibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age_eligible: bool           # 서비스 이용 연령(만 19세 이상)인가
    diagnosed_cad: bool          # 협심증·심근경색 등 관상동맥질환 진단 여부
    emergency_flag: bool = False  # 응급 증상 "예"·"잘 모르겠습니다" (증상 원문은 받지 않는다)
    emergency_acknowledged: bool = False  # 응급 안내를 확인하고 "그래도 진행"을 눌렀는가


class EligibilityResult(BaseModel):
    result_code: str   # eligible / age_out / diagnosed / emergency
    age_eligible: bool
    diagnosed_cad: bool
    emergency_flag: bool
    emergency_acknowledged_at: datetime | None
    assessed_at: datetime


def _result_code(req: EligibilityRequest) -> str:
    """응급이 가장 먼저(안전), 그다음 나이, 관상동맥질환. 모델별 제외 기준은 모델_연결_명세를 따른다."""
    if req.emergency_flag:
        return "emergency"
    if not req.age_eligible:
        return "age_out"
    if req.diagnosed_cad:
        return "diagnosed"
    return "eligible"


def _to_result(row) -> EligibilityResult:
    return EligibilityResult(
        result_code=row.result_code, age_eligible=row.age_eligible, diagnosed_cad=row.diagnosed_cad,
        emergency_flag=row.emergency_flag, emergency_acknowledged_at=row.emergency_acknowledged_at, assessed_at=row.assessed_at,
    )


@router.get("/users/me/eligibility", response_model=DataResponse[EligibilityResult])
async def get_eligibility(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)):
    """가장 최근 대상 확인. 없으면 404."""
    row = await eligibility_repository.get_latest(db, user_id)
    if row is None:
        raise AppError(404, "ELIGIBILITY_NOT_FOUND", "대상 확인 기록이 없습니다.")
    return DataResponse(data=_to_result(row))


@router.put("/users/me/eligibility", response_model=DataResponse[EligibilityResult])
async def save_eligibility(
    req: EligibilityRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(async_get_db)
):
    """대상 확인 한 건을 새로 쌓는다 (이력으로 남고, 조회는 가장 최근 것)."""
    now = utcnow()
    acknowledged_at = now if (req.emergency_flag and req.emergency_acknowledged) else None
    row = await eligibility_repository.add(
        db, user_id, _result_code(req), req.age_eligible, req.diagnosed_cad, req.emergency_flag, acknowledged_at, now
    )
    await db.commit()
    return DataResponse(data=_to_result(row))
