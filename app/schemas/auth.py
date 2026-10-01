""" 회원가입/로그인 신청서와 결과지 양식 """
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field

class SignupRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")

    email: EmailStr
    password: str =Field(min_length=8, max_length=72, description="8자 이상")
    birth_date: date=Field(description="만 14세 미만 확인용 ")


class SignupResult(BaseModel):
    user_id: str

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

class TokenResult(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 팔찌 유효 시간(초)