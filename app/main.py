import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from starlette.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.apis.health import router as health_router
from app.apis.survey import router as survey_router
from app.apis.prediction_job import router as prediction_job_router
from app.apis.account import router as account_router
from app.apis.calendar import router as calendar_router
from app.apis.consent import require_health_consent, router as consent_router
from app.apis.eligibility import router as eligibility_router
from app.apis.admin import router as admin_router
from app.apis.admin_overview import router as admin_overview_router
from app.apis.inquiry import router as inquiry_router
from app.apis.guest_inquiry import router as guest_inquiry_router
from app.apis.notice import admin_router as notice_admin_router, public_router as notice_router
from app.apis.pie import router as pie_router
from app.apis.community import router as community_router
from app.apis.common_challenge import admin_router as common_challenge_admin_router, router as common_challenge_router
from app.apis.home import router as home_router
from app.apis.community_admin import admin_router as community_admin_router, posts_router as community_posts_admin_router

from app.apis.auth import router as auth_router
from app.apis.challenge import router as challenge_router
from app.core.db.databases import AsyncSessionLocal
from app.core.errors import register_error_handlers
from app.services import admin_registry_service
from app.apis.character import router as character_router
from app.apis.party import router as party_router
from app.core.config import check_required_secrets
from app.apis.push import router as push_router

BASE_DIR = Path(__file__).resolve().parent.parent

# compose 볼륨으로 마운트되므로 없을 때만 만든다
(BASE_DIR / "static").mkdir(exist_ok=True)
(BASE_DIR / "media").mkdir(exist_ok=True)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """서버가 켜질 때 관리자 목록의 변화(권한 부여·회수)를 관리자 행위 기록에남긴다. 실패해도 서버는 켠다."""
    check_required_secrets()   # 비밀 열쇠가 기본값이면 여기서 멈춘다 (위 '실패해도 켠다'와 달리 반드시 멈춤)
    try:
        async with AsyncSessionLocal() as db:
            await admin_registry_service.sync_admin_log(db)
    except Exception:
        logging.getLogger(__name__).exception("관리자 권한 기록 실패")
    yield


app = FastAPI(title="PAEON API", lifespan=lifespan)
register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router,prefix="/v1")
app.include_router(health_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(survey_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(prediction_job_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(calendar_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(account_router, prefix="/v1")
app.include_router(consent_router, prefix="/v1")
app.include_router(eligibility_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(challenge_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(inquiry_router, prefix="/v1")
app.include_router(notice_router, prefix="/v1")
app.include_router(notice_admin_router, prefix="/v1")
app.include_router(pie_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(community_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(community_admin_router, prefix="/v1")
# 공통 챌린지 참여·인증은 건강 관련 활동이라, 개인 챌린지·파티처럼 건강정보 동의를 철회했으면 막는다(멘토링 10/20 지적)
app.include_router(common_challenge_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(common_challenge_admin_router, prefix="/v1")
app.include_router(guest_inquiry_router, prefix="/v1")
app.include_router(admin_router, prefix="/v1")
app.include_router(admin_overview_router, prefix="/v1")
app.include_router(home_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(character_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(party_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.include_router(community_posts_admin_router, prefix="/v1")
app.include_router(push_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")


@app.get("/healthcheck", status_code=200, include_in_schema=False)
async def healthcheck():
    return {"status": "ok"}
