""" 비밀번호 해시 도구. 비밀번호는 bcrypt 해시로만 저장 """
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings
from cryptography.fernet import Fernet

def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    """팔찌(액세스 토큰)를 만든다."""
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """팔찌가 진짜면 회원 번호, 가짜거나 만료됐으면 None."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    return payload.get("sub")


def new_refresh_token() -> str:
    """쿠폰(리프레시 토큰)을 만든다. 아무도 맞힐 수 없는 무작위 글자."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """쿠폰을 SHA-256으로 간다. 같은 쿠폰은 항상 같은 결과가 나온다."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _fernet() -> Fernet:
    """보호자 정보용 자물쇠 상자. 열쇠는 .env의 GUARDIAN_ENC_KEY."""
    if not settings.GUARDIAN_ENC_KEY:
        raise RuntimeError("GUARDIAN_ENC_KEY가 .env에 없습니다.")
    return Fernet(settings.GUARDIAN_ENC_KEY)


def encrypt_text(plain: str) -> str:
    """글자를 잠근다. DB의 *_enc 칸에 넣는다."""
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_text(locked: str) -> str:
    """잠긴 글자를 연다. 보호자에게 연락할 때만 쓴다."""
    return _fernet().decrypt(locked.encode("utf-8")).decode("utf-8")