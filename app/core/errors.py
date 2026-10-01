""" API 명세서 공통 실패 응답 """

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code=status_code
        self.code=code
        self.message=message

def _error_body(code: str, message: str, details: list | None=None)->dict:
    body={"error": {"code":code, "message":message}}
    if details:
        body["error"]["details"]=details

    return body

def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details=[
            {"field": ".".join(str(p) for p in err["loc"] if p != "body"), "reason": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_body("VALIDATION_ERROR", "입력값을 확인해 주세요. ", details),
        )