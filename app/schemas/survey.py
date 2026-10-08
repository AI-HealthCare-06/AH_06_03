"""설문 결과지·신청서 양식."""
from pydantic import BaseModel, ConfigDict, Field, model_validator


class OptionResult(BaseModel):
    """🔘 보기 하나."""
    option_id: str
    option_code: str
    option_text: str


class QuestionResult(BaseModel):
    """❓ 질문 하나 (안에 보기들)."""
    question_id: str
    question_code: str
    question_text: str
    required: bool
    answer_type: str                 # "single_select" 또는 "number"
    num_min: int | None = None       # 숫자 질문만
    num_max: int | None = None
    options: list[OptionResult]


class SurveyResult(BaseModel):
    """📚 설문지 하나 (안에 질문들)."""
    survey_version_id: str
    survey_type: str
    version: str
    questions: list[QuestionResult]

class SurveyStartRequest(BaseModel):
    """📋 답안지 받기 신청서."""
    model_config = ConfigDict(extra="forbid")

    survey_version_id: str
    health_record_id: str | None = None


class SurveyInstanceResult(BaseModel):
    """📋 답안지 결과지."""
    survey_instance_id: str
    survey_version_id: str
    status: str

class ResponseItem(BaseModel):
    """✔️ 답 하나. 고르는 질문은 option_id, 숫자 질문은 value_num (둘 중 하나만)."""
    model_config = ConfigDict(extra="forbid")

    question_id: str
    option_id: str | None = None
    value_num: float | None = None

    @model_validator(mode="after")
    def check_one_answer(self) -> "ResponseItem":
        has_option = self.option_id is not None
        has_num = self.value_num is not None
        if has_option == has_num:
            raise ValueError("보기(option_id)와 숫자(value_num) 중 하나만 보내 주세요.")
        return self


class ResponsesRequest(BaseModel):
    """✔️ 답 여러 개 적기 신청서."""
    model_config = ConfigDict(extra="forbid")

    responses: list[ResponseItem] = Field(min_length=1)