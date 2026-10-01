""" 비밀번호 해시 도구. 비밀번호는 bcrypt 해시로만 저장 """
from datetime import UTC, datetime

import bcrypt

def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

