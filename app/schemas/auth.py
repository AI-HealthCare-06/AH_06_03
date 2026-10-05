""" 회원가입/로그인 신청서와 결과지 양식 """
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

class SignupRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")

    email: EmailStr
    password: str =Field(min_length=8, max_length=72, description="8자 이상")
    birth_date: date=Field(description="만 14세 미만 확인용 ")

    # 만 14세 미만만: 법정대리인 정보 (세 칸은 다 채우거나 다 비운다)
    guardian_name: str | None = Field(default=None, max_length=50)
    guardian_relation: Literal["parent", "legal_guardian"] | None = None
    guardian_contact: str | None = Field(default=None, max_length=100, description="휴대폰 번호 또는 이메일")

    @model_validator(mode="after")
    def check_guardian_fields(self) -> "SignupRequest":
        filled = [self.guardian_name, self.guardian_relation, self.guardian_contact]
        if any(v is not None for v in filled) and not all(v is not None for v in filled):
            raise ValueError("보호자 정보는 이름·관계·연락처를 모두 입력해야 합니다.")
        return self


class SignupResult(BaseModel):
    user_id: str
    guardian_verification_status: str | None = None  # 미성년자면 "pending", 성인이면 None

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

class TokenResult(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 팔찌 유효 시간(초)

class MeResult(BaseModel):
    user_id: str
    email: str
    sex: str | None
    birth_date: date

class ProfileUpdateRequest(BaseModel):
    """내 프로필 고치기 신청서 (W04에서 성별 입력)."""
    model_config = ConfigDict(extra="forbid")

    sex: Literal["male", "female"]


