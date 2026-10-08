"""챌린지 창구. W09 챌린지 선택 · W10 챌린지 수행."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.apis.deps import get_current_user_id
from app.core.db.databases import async_get_db
from app.schemas.challenge import (
    CycleResult, CycleStartRequest, CycleStopRequest, CycleSummary, LogRequest, LogResult, ReassessmentRequest,
    RecommendationResult, ReviewResult,
)
from app.schemas.common import DataResponse
from app.services import challenge_service

router = APIRouter(tags=["challenge"])


@router.get("/challenges/recommendations", response_model=DataResponse[RecommendationResult])
async def get_recommendations(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    """고정 미션 2개 + 선택 후보 + 제외 사유 (최근 건강정보·설문 기준)."""
    return DataResponse(data=await challenge_service.get_recommendation(db, user_id))


@router.post("/challenges/cycles", status_code=status.HTTP_201_CREATED, response_model=DataResponse[CycleResult])
async def start_cycle(
    req: CycleStartRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await challenge_service.start_cycle(db, user_id, req.selected_code))


@router.get("/challenges/cycles", response_model=DataResponse[list[CycleSummary]])
async def list_cycles(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await challenge_service.list_cycles(db, user_id))


@router.get("/challenges/cycles/current", response_model=DataResponse[CycleResult])
async def get_current_cycle(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await challenge_service.get_current_cycle(db, user_id))


@router.get("/challenges/cycles/{cycle_id}", response_model=DataResponse[CycleResult])
async def get_cycle(
    cycle_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await challenge_service.get_cycle(db, user_id, cycle_id))


@router.put("/challenges/cycles/current/logs/{challenge_code}", response_model=DataResponse[LogResult])
async def record_log(
    challenge_code: str,
    req: LogRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    """오늘 기록 저장·수정. 날짜는 서버가 오늘로 정한다 (지난 날짜는 고칠 수 없음)."""
    return DataResponse(
        data=await challenge_service.record_log(db, user_id, challenge_code, req.answer, req.quantity, req.note)
    )


@router.post("/challenges/cycles/current/stop", response_model=DataResponse[CycleResult])
async def stop_cycle(
    req: CycleStopRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    return DataResponse(data=await challenge_service.stop_cycle(db, user_id, req.reason_code, req.note))


@router.post(
    "/challenges/cycles/{cycle_id}/reassessment",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[ReviewResult],
)
async def submit_reassessment(
    cycle_id: str,
    req: ReassessmentRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    """4주 재입력 (가이드 §6.1) → 모델 A·B 재예측 → 전후 비교."""
    items = [m.model_dump() for m in req.measurements]
    return DataResponse(
        data=await challenge_service.submit_reassessment(db, user_id, cycle_id, req.examination_date, items)
    )


@router.get("/challenges/cycles/{cycle_id}/review", response_model=DataResponse[ReviewResult])
async def get_review(
    cycle_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(async_get_db),
):
    """W11-2 전후 비교."""
    return DataResponse(data=await challenge_service.get_review(db, user_id, cycle_id))
