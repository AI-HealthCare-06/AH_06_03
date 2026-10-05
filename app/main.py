from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.apis.health import router as health_router
from app.apis.survey import router as survey_router


from app.apis.prediction import router as prediction_router
from app.apis.auth import router as auth_router
from app.core.errors import register_error_handlers

BASE_DIR = Path(__file__).resolve().parent.parent

# compose 볼륨으로 마운트되므로 없을 때만 만든다
(BASE_DIR / "static").mkdir(exist_ok=True)
(BASE_DIR / "media").mkdir(exist_ok=True)

app = FastAPI(title="PAEON API")
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


app.include_router(prediction_router, prefix="/v1")
app.include_router(auth_router,prefix="/v1")
app.include_router(health_router, prefix="/v1")
app.include_router(survey_router, prefix="/v1") 
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")


@app.get("/healthcheck", status_code=200, include_in_schema=False)
async def healthcheck():
    return {"status": "ok"}
