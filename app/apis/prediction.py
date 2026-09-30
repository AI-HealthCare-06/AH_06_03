"""/predict 창구.
 
주문을 받아 서비스에 넘기고, 결과를 돌려주기만 한다. 계산은 하지 않는다.
"""

from fastapi import APIRouter

from app.schemas.prediction import PredictRequest, PredictResponse
from app.services import prediction_service

router = APIRouter(tags=["prediction"])

@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="모델 A/B 예측",
    description="건강정보를 받아 모델 A(10년 관싱동맥질환 위험)와 모델 B(현재 경계군과 닮은 정도) 결과를 따로 돌려준다",

)
def predict(req:PredictRequest)->PredictResponse:
    return prediction_service.predict(req)

