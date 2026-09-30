"""예측 처리 로직.
 
두 모델을 따로 부르고, 결과는 가공하지 않고 그대로 담는다.
한 모델이 오류로 멈춰도 다른 모델 결과는 살린다. (모델_연결_명세 §2.1, NFR-ARCH-003)
"""

import logging # 무슨 일이 있었는지, 특히 오류 발생 시 기록

from app.ml import predictor
from app.schemas.prediction import PredictResponse, ModelResult, PredictRequest

logger = logging.getLogger(__name__)

FAILED_MESSAGE = "예측 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

# 모델 하나를 안전하게 실행하는 함수
def _run_safely(model_code: str, run, user: dict) -> ModelResult:
    """모델을 실행하고 결과를 ModelResult로 감싸서 반환한다.
    모델이 오류를 내면 ModelResult.status=failed로 반환한다.
    """
    try:
        return ModelResult(**run(user))
    except Exception:
        logger.exception("%s 예측 실패", model_code)
        return ModelResult(model_code=model_code, status="failed", error=FAILED_MESSAGE)

# 본체 함수
def predict(req:PredictRequest) -> PredictResponse:
    """두 모델을 실행하고 결과를 담아 반환한다"""
    user = req.model_dump() # 접수 서류를 짝 모음으로 변환
    return PredictResponse(
        model_a=_run_safely("MODEL_A", predictor.run_model_a, user),
        model_b=_run_safely("MODEL_B", predictor.run_model_b, user)
    ) # 두 모델 실행 후 결과 담기


