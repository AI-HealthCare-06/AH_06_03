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


from app.apis.prediction import router as prediction_router
from app.apis.auth import router as auth_router
from app.apis.challenge import router as challenge_router
from app.core.db.databases import AsyncSessionLocal
from app.core.errors import register_error_handlers
from app.services import admin_registry_service

BASE_DIR = Path(__file__).resolve().parent.parent

# compose 볼륨으로 마운트되므로 없을 때만 만든다
(BASE_DIR / "static").mkdir(exist_ok=True)
(BASE_DIR / "media").mkdir(exist_ok=True)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """서버가 켜질 때 관리자 목록의 변화(권한 부여·회수)를 관리자 행위 기록에 남긴다. 실패해도 서버는 켠다."""
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


app.include_router(prediction_router, prefix="/v1", dependencies=[Depends(require_health_consent)])
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
app.include_router(guest_inquiry_router, prefix="/v1")
app.include_router(admin_router, prefix="/v1")
app.include_router(admin_overview_router, prefix="/v1")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")


@app.get("/healthcheck", status_code=200, include_in_schema=False)
async def healthcheck():
    return {"status": "ok"}
