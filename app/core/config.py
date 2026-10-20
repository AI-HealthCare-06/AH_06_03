import logging
import secrets

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
    # 같은 IP에서 15분 안에 이만큼 로그인을 틀리면 그 IP를 잠시 막는다. 체험 안내처럼 여러 명이 같은 와이파이로
    # 로그인하는 날에는 .env에서 늘린다 (계정마다 5번 제한은 따로 있어서 늘려도 비밀번호 맞히기는 막힌다).
    LOGIN_MAX_FAILS_PER_IP: int = 50
    # 운영 알림(신고 누적 자동 숨김 등)을 보낼 디스코드 웹후크 주소. 비우면 보내지 않는다. 실제 값은 .env에만 적는다.
    ADMIN_ALERT_WEBHOOK: str = ""

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

# 로그인 서명 키가 .env에 없거나 저장소에 공개된 기본값이면 그대로 쓰지 않는다.
# 기본값으로 서명하면 누구나 아무 계정(관리자 포함)의 토큰을 만들 수 있기 때문이다.
# 대신 실행할 때마다 임의 키를 만든다: 재시작하면 모두 다시 로그인해야 하지만 위조는 불가능하다.
# (uvicorn 프로세스가 하나라 한 번 만든 키를 모든 요청이 같이 쓴다. 운영 서버는 .env에 진짜 키가 있어 해당 없음)
DEFAULT_JWT_SECRET = "change-me-jwt-secret"
if settings.JWT_SECRET in ("", DEFAULT_JWT_SECRET):
    settings.JWT_SECRET = secrets.token_hex(32)
    logging.getLogger(__name__).warning("JWT_SECRET가 .env에 없거나 기본값이라 임시 키를 만들었습니다. 재시작하면 모두 다시 로그인해야 합니다.")
