"""/predict 입력·출력 양식.
 
기준 문서: modeling/handoff/모델_연결_명세.md
  - 입력: §1.1 필드 목록, §1.2 선택지 → 값 변환표
  - 출력: §3 출력 명세
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 선택지 값
Sex = Literal["M", "F"]
Smoking= Literal["current", "former", "never"]
HtnStatus = Literal["none", "diagnosed_untreated", "treated"]
ParentHtn= Literal["yes", "no", "unknown"]
DrinlFreq = Literal[
    "never_lifetime", "none_past_year", "It_montly", "monthly",
    "2_4_per_month", "2_3_per_week", "4plus_per_week",
]
DrinkAmount=Literal["1_2", "3_4", "5_6", "7_9", "10plus"]
Breakfast=Literal["5_7", "3_4", "1_2", "0"]
EatOut=Literal[
    "2plus_per_day", "1_per_day", "5_6_per_week", "3_4_per_week",
    "1_2_per_week", "1_3_per_month", "It_monthly",
]


# 입력
class PredictRequest(BaseModel):
    # 양식에 없는 이름이 오면 422
    model_config = ConfigDict(extra="forbid")

    # 프로필
    # 나이는 넓게 검사, 모델 적용 연령 밖이면 422가 아니라 skipped로 돌려준다
    age: int = Field(ge=0, le=120, description="나이(세)")
    sex: Sex

    # 건강정보 입력
    height_cm: float=Field(ge=120, le=220, description="키(cm)")
    weight_kg: float=Field(ge=30, le=200, description="몸무게(kg)")
    sbp: float=Field(ge=60, le=260, description="수축기혈압(mmHg)")
    dbp: float=Field(ge=30, le=160, description="이완기혈압(mmHg)")
    total_chol: float=Field(ge=50, le=600, description="총콜레스테롤(mg/dL)")
    smoking: Smoking
    diabetes: bool
    htn_status: HtnStatus
    parent_htn: ParentHtn
    drink_freq: DrinlFreq

    # 비어도 예측은 수행하고 missing_features로 알려주는 항목
    # | 는 또는 이라는 의미, none은 비워도 되는 칸이라는 의미
    waist_cm: float | None = Field(default=None, ge=50, le=150, description="허리둘레(cm)")
    drink_amount: DrinkAmount | None = Field(default=None, description="한 번 음주량. 음주자만")
    hdl: float | None = Field(default=None, ge=5, le=200, description="HDL(mg/dL). 모델은 사용하지 않음")
    fasting_glucose: float | None = Field(default=None, ge=30, le=600, description="공복혈당(mg/dL). 모델은 사용하지 않음")

    # 생활습관 설문
    breakfast: Breakfast | None = None
    eatout: EatOut | None = None
    moderate_min_per_week: float | None = Field(default=None, ge=0, le=5000)
    vigorous_min_per_week: float | None = Field(default=None, ge=0, le=5000)
    aerobic: Literal[0, 1] | None = Field(default=None, description="분 대신 직접 보낼 때")

# 출력
# 점수에 영향을 준 이유
class Factor(BaseModel):
    code: str # 컴퓨터용 이름
    label: str # 사람이 읽는 이름
    value: float | int | str | None = None
    value_label: str | None = None
    contribution: float # 점수에 기여한 정도
    direction: Literal["risk_increase","protective"]
    modifiable: bool # 노력으로 바꿀 수 있는가?
    direction_matches_expectation: bool # 상식과 같은 방향인가?
    display_rank: int # 화면에 보여줄 순서


# 모델 하나의 결과 / 모델 A와 모델 B 각각에 대해 하나씩
class ModelResult(BaseModel):
    model_code:Literal["MODEL_A", "MODEL_B"] # 어떤 모델인지
    model_version:str | None=None # 모델 버전
    status: Literal["completed", "skipped", "failed"] # 상태
    skip_reason:Literal["age_out_of_range", "htn_diagnosed"] | None=None # 스킵한 이유
    probability:float | None=None # 점수
    risk_level:Literal["normal", "borderline", "high"] | None=None # 신호등
    percentile:float | None=None # 같은 나이/성별 중 등수
    vascular_age: float | None = None # 혈관 나이
    factors:list[Factor]=[] # 요인들
    top_risk_factor: Factor | None=None # 1등 위험 요인
    top_modifiable_factor: Factor | None=None # 1등으로 바꿀 수 있는 요인
    missing_features:list[str]=[] # 비어서 대신 채운 칸들의 목록
    error:str | None=None # 오류가 났을 때 오류 내용

# 안내 문구
DISCLAIMER = "이 결과는 진단이 아닌 선별 정보입니다. 정확한 판단은 의료기관에서 확인하세요"

# 최종 결과지
class PredictResponse(BaseModel):
    model_a: ModelResult
    model_b: ModelResult
    disclaimer: str = DISCLAIMER


class PredictEnvelope(BaseModel):
    """API 명세서 공통 규칙: 성공 응답은 {"data": ...}로 감싼다."""
    data: PredictResponse

class PredictionJobResult(BaseModel):
    """🎫 번호표 결과지: 번호표 정보 + 모델별 결과."""
    prediction_job_id: str
    status: str
    model_a: ModelResult
    model_b: ModelResult
    disclaimer: str = DISCLAIMER

class PredictionJobRequest(BaseModel):
    """🎫 예측 신청서."""
    model_config = ConfigDict(extra="forbid")

    health_record_id: str
    survey_instance_id: str | None = None
    request_type: Literal["initial", "interim", "full", "manual"] = "initial"
    