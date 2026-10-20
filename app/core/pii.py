"""개인정보 컬럼 암호화 (멘토링 10/13·10/20: 개인정보는 컬럼 단위로 암호화).

- 키는 서버 .env에만 둔다. 보호자 정보 키(GUARDIAN_ENC_KEY)와 따로 두어, 한 키가 새도 다른 정보까지 열리지 않게 한다.
  - PII_ENC_KEY  : 개인정보를 잠그는 키(Fernet). 잃으면 잠근 값을 다시 열 수 없다.
  - PII_HASH_KEY : 이메일 찾기용 지문(HMAC-SHA256)을 만드는 키. 잃으면 아무도 로그인할 수 없다.
  두 키 모두 키체인과 비밀번호 관리자에 사본을 둔다.
- 잠근 값은 같은 글자도 저장할 때마다 달라져서 검색이 안 된다. 그래서 이메일은 찾기용 지문 칸(email_hash)을 따로 둔다.
"""
import hashlib
import hmac
from functools import lru_cache

from cryptography.fernet import Fernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.core.config import settings


def require_keys() -> None:
    """키가 없으면 바로 멈춘다(빈 키로 잠그거나 지문을 만들면 안 되므로)."""
    if not settings.PII_ENC_KEY or not settings.PII_HASH_KEY:
        raise RuntimeError("PII_ENC_KEY·PII_HASH_KEY가 .env에 없습니다.")


def normalize_email(email: str) -> str:
    """이메일 정리: 앞뒤 공백을 지우고 소문자로. 가입·로그인·관리자 확인·지문이 모두 이 함수를 쓴다."""
    return email.strip().lower()


def email_hash(email: str) -> str:
    """이메일 찾기용 지문. 같은 이메일(정리 후)은 항상 같은 값이라 로그인·중복 확인에 쓴다."""
    require_keys()
    return hmac.new(settings.PII_HASH_KEY.encode("utf-8"), normalize_email(email).encode("utf-8"),
                    hashlib.sha256).hexdigest()


@lru_cache(maxsize=4)
def _fernet(key: str) -> Fernet:
    return Fernet(key)


def encrypt(plain: str) -> str:
    require_keys()
    return _fernet(settings.PII_ENC_KEY).encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt(locked: str) -> str:
    require_keys()
    return _fernet(settings.PII_ENC_KEY).decrypt(locked.encode("utf-8")).decode("utf-8")


class EncryptedText(TypeDecorator):
    """저장할 때 자동으로 잠그고, 읽을 때 자동으로 푸는 칸. 서비스 코드는 평소처럼 글자를 넣고 읽는다.
    DB 안에서는 이 값으로 검색·정렬할 수 없다(잠긴 글자이므로)."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else encrypt(str(value))

    def process_result_value(self, value, dialect):
        return None if value is None else decrypt(value)
