from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_USER: str = "paeon"
    DB_PASSWORD: str = "change-me"
    DB_HOST: str = "localhost"
    DB_PORT: str = "3306"
    DB_NAME: str = "paeon"
    # 로그인 토큰 (NFR-SEC-002). 실제 값은 .env에만 적는다.
    JWT_SECRET: str = "change-me-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    # 보호자 정보 암호화 열쇠 (Fernet). 실제 값은 .env에만 적는다.
    GUARDIAN_ENC_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    # 관리자 이메일 목록 (쉼표로 구분). 비어 있으면 아무도 관리자가 아니다. 실제 값은 .env에만 적는다.
    ADMIN_EMAILS: str = ""

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

