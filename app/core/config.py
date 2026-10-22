from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_USER: str = "paeon"
    DB_PASSWORD: str = "change-me"
    DB_HOST: str = "localhost"
    DB_PORT: str = "3306"
    DB_NAME: str = "paeon"
    # 로그인 토큰 (NFR-SEC-002). 실제 값은 .env에만 적는다.
    JWT_SECRET: str = "change-me-jwt-secret"   # 기본값이면 서버가 안 켜진다 (check_required_secrets)
    JWT_ALGORITHM: str = "HS256"
    # 보호자 정보 암호화 열쇠 (Fernet). 실제 값은 .env에만 적는다.
    GUARDIAN_ENC_KEY: str = ""
    # 개인정보 컬럼 암호화 키 (app/core/pii.py). 보호자 키와 따로 둔다. 실제 값은 .env에만 적는다.
    PII_ENC_KEY: str = ""     # 잠그기(Fernet). 잃으면 잠근 값을 다시 열 수 없음
    PII_HASH_KEY: str = ""    # 이메일 찾기용 지문(HMAC). 잃으면 아무도 로그인할 수 없음
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    # 관리자 이메일 목록 (쉼표로 구분). 비어 있으면 아무도 관리자가 아니다. 실제 값은 .env에만 적는다.
    ADMIN_EMAILS: str = ""
    # 같은 IP에서 15분 안에 이만큼 로그인을 틀리면 그 IP를 잠시 막는다. 체험 안내처럼 여러 명이 같은 와이파이로
    # 로그인하는 날에는 .env에서 늘린다 (계정마다 5번 제한은 따로 있어서 늘려도 비밀번호 맞히기는 막힌다).
    LOGIN_MAX_FAILS_PER_IP: int = 50
    # 운영 알림(신고 누적 자동 숨김 등)을 보낼 디스코드 웹후크 주소. 비우면 보내지 않는다. 실제 값은 .env에만 적는다.
    ADMIN_ALERT_WEBHOOK: str = ""
    # 지인 체험 전용: 3일치 챌린지 기록을 남기면 나머지 4주를 같은 비율로 채우고 사이클을 끝낸다. 정식 배포에서는 꺼 둔다(0).
    DEMO_AUTOFILL: bool = False
    # 체험 마지막 날(YYYY-MM-DD). 이 날이 지나면 자동 채움을 멈추고, 화면은 3일을 못 채운 사람에게 체험 종료 안내를 보여 준다. 비우면 끝나지 않는다.
    DEMO_AUTOFILL_END: str = ""
    # 팀 사전 점검 전용(로컬·임시 서버): 서버의 "오늘"을 이만큼 앞당긴다(1이면 내일, 2면 모레). 지인이 쓰는 서버에서는 반드시 0(기본값)으로 둔다.
    DEMO_DAY_OFFSET: int = 0

    @property
    def demo_end(self):
        from datetime import date
        import logging
        if not self.DEMO_AUTOFILL_END.strip():
            return None
        try:
            return date.fromisoformat(self.DEMO_AUTOFILL_END.strip())
        except ValueError:      # 형식이 틀리면 요청마다 500이 나지 않게 경고만 하고 끝나지 않은 것으로 본다
            logging.getLogger(__name__).warning("DEMO_AUTOFILL_END 형식이 잘못돼 무시합니다(YYYY-MM-DD): %r", self.DEMO_AUTOFILL_END)
            return None

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

DEFAULT_JWT_SECRET = "change-me-jwt-secret"


def check_required_secrets(s: "Settings" = None) -> None:
    """서버가 켜질 때 비밀 열쇠가 기본값이면 멈춘다.
    JWT_SECRET이 누구나 아는 기본값이면 로그인 팔찌를 위조할 수 있어서(아무 회원으로 로그인), 켜지지 않게 막는다."""
    s = s or settings
    if not s.JWT_SECRET or s.JWT_SECRET == DEFAULT_JWT_SECRET:
        raise RuntimeError("JWT_SECRET이 비어 있거나 기본값이에요. 서버 .env에 긴 무작위 값을 넣어 주세요.")

