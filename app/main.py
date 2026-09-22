from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent

# compose 볼륨으로 마운트되므로 없을 때만 만든다
(BASE_DIR / "static").mkdir(exist_ok=True)
(BASE_DIR / "media").mkdir(exist_ok=True)

app = FastAPI(title="PAEON API")

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")


@app.get("/healthcheck", status_code=200, include_in_schema=False)
async def healthcheck():
    return {"status": "ok"}
