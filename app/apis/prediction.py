"""/v1/predict 임시 창구.
 
모델 연결 확인용. API 명세서의 정식 흐름(/health/records → /predictions/jobs)이
완성되면 지운다. 계산은 하지 않고, 받고 넘기고 돌려주기만 한다.

"""

from fastapi import APIRouter

from app.schemas.prediction import PredictRequest, PredictEnvelope
from app.services import prediction_service

router = APIRouter(tags=["prediction"])

@router.post(
    "/predict",
    response_model=PredictEnvelope,
    summary="[임시] 모델 A/B 예측",
    description="모델 연결 확인용 임시 창구. 정식 흐름은 /health/records → /predictions/jobs.",

)
def predict(req:PredictRequest)->PredictEnvelope:
    return PredictEnvelope(data=prediction_service.predict(req))

