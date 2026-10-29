"""예측 처리 로직.
 
두 모델을 따로 부르고, 결과는 가공하지 않고 그대로 담는다.
한 모델이 오류로 멈춰도 다른 모델 결과는 살린다. (모델_연결_명세 §2.1, NFR-ARCH-003)
"""

import logging # 무슨 일이 있었는지, 특히 오류 발생 시 기록

from app.ml import predictor
from app.schemas.prediction import PredictResponse, ModelResult

logger = logging.getLogger(__name__)

FAILED_MESSAGE = "예측 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

def _drop_imputed_factors(r: dict) -> dict:
    """입력하지 않아 대푯값으로 채운 항목은 요인 설명에서 뺀다 (확률은 그대로)."""
    missing = set(r.get("missing_features") or [])
    if not missing or not r.get("factors"):
        return r
    factors = [f for f in r["factors"] if f["code"] not in missing]
    for i, f in enumerate(factors, 1):
        f["display_rank"] = i
    pos = [f for f in factors if f["contribution"] > 0]
    r["factors"] = factors
    r["top_risk_factor"] = pos[0] if pos else None
    r["top_modifiable_factor"] = next((f for f in pos if f["modifiable"]), None)
    return r

# 모델 하나를 안전하게 실행하는 함수
def _run_safely(
    model_code: str,
    run,
    user: dict,
    version: str,
) -> ModelResult:
    """한 모델을 지정한 버전으로 안전하게 실행한다."""
    try:
        result = ModelResult(**_drop_imputed_factors(run(user, version)))
        result.model_updated_on = predictor.model_release_info(
            model_code,
            version,
        ).get("updated_on")
        return result
    except Exception:
        logger.exception("%s 예측 실패", model_code)
        return ModelResult(
            model_code=model_code,
            model_version=version,
            status="failed",
            error=FAILED_MESSAGE,
            model_updated_on=predictor.model_release_info(
                model_code,
                version,
            ).get("updated_on"),
        )

# 본체 함수
def predict_dict(
    user: dict,
    model_versions: dict[str, str] | None = None,
) -> PredictResponse:
    """번역된 사전을 받아 지정한 버전의 모델 A·B를 따로 실행한다."""
    versions = model_versions or predictor.CURRENT_VERSION

    return PredictResponse(
        model_a=_run_safely(
            "MODEL_A",
            predictor.run_model_a,
            user,
            versions["MODEL_A"],
        ),
        model_b=_run_safely(
            "MODEL_B",
            predictor.run_model_b,
            user,
            versions["MODEL_B"],
        ),
    )
