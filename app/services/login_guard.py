"""로그인 시도 제한: 비밀번호를 짧은 시간에 여러 번 틀리면 잠시 막는다 (비밀번호 맞히기 공격 방지).

- 같은 이메일: 15분 안에 5번 틀리면 그 이메일로는 잠시(최대 15분) 로그인할 수 없다. 로그인에 성공하면 처음부터 다시 센다.
- 같은 IP: 15분 안에 50번(설정 LOGIN_MAX_FAILS_PER_IP) 틀리면 그 IP에서는 잠시 로그인할 수 없다
  (여러 계정을 번갈아 찔러 보는 것을 막는다). 같은 와이파이에서 여러 명이 로그인하는 날을 생각해 넉넉히 두었다.
- 막혀 있는 동안의 시도는 비밀번호를 확인하지도, 실패로 세지도 않는다 (막힘이 끝없이 늘어나지 않게).
- 없는 이메일도 똑같이 세서, 응답만 보고 가입 여부를 알 수 없게 한다.

실패 횟수는 DB가 아니라 이 프로세스의 메모리에만 둔다. "로그인 실패는 접속 기록을 남기지 않는다"는 팀 결정
(tests/test_access_and_admin_log.py)을 지키기 위해서다. 서버가 프로세스 하나(uvicorn 1개)로 돌아서 메모리로 충분하고,
재배포·재시작하면 횟수가 0으로 돌아가지만 그건 공격자가 일으킬 수 없는 일이라 괜찮다.
uvicorn을 여러 프로세스로 늘리면 횟수가 프로세스마다 따로 세지므로, 그때는 DB나 Redis로 옮겨야 한다.
"""
from collections import deque
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import utcnow

WINDOW = timedelta(minutes=15)
MAX_PER_ACCOUNT = 5
MAX_KEYS = 10_000          # 메모리가 끝없이 커지지 않게: 이보다 많아지면 지난 기록부터 정리한다

TOO_MANY = AppError(429, "AUTH_TOO_MANY_ATTEMPTS", "로그인 시도가 너무 많아요. 15분 뒤에 다시 시도해 주세요.")

_by_email: dict[str, deque[datetime]] = {}
_by_ip: dict[str, deque[datetime]] = {}


def _recent(book: dict[str, deque[datetime]], key: str, now: datetime) -> int:
    q = book.get(key)
    if not q:
        return 0
    while q and q[0] <= now - WINDOW:
        q.popleft()
    if not q:
        del book[key]
        return 0
    return len(q)


def _tidy(book: dict[str, deque[datetime]], now: datetime) -> None:
    if len(book) > MAX_KEYS:
        for key in [k for k, q in book.items() if not q or q[-1] <= now - WINDOW]:
            del book[key]


def check(email: str, ip: str | None) -> None:
    """막혀 있으면 TOO_MANY. 비밀번호를 확인하기 전에 부른다."""
    now = utcnow()
    if _recent(_by_email, email.strip().lower(), now) >= MAX_PER_ACCOUNT:
        raise TOO_MANY
    if ip and _recent(_by_ip, ip, now) >= settings.LOGIN_MAX_FAILS_PER_IP:
        raise TOO_MANY


def record_failure(email: str, ip: str | None) -> None:
    now = utcnow()
    _by_email.setdefault(email.strip().lower(), deque()).append(now)
    if ip:
        _by_ip.setdefault(ip, deque()).append(now)
    _tidy(_by_email, now)
    _tidy(_by_ip, now)


def record_success(email: str) -> None:
    """로그인에 성공하면 그 이메일의 틀린 횟수를 지운다 (IP 쪽 횟수는 그대로)."""
    _by_email.pop(email.strip().lower(), None)


def reset() -> None:
    """모든 횟수를 지운다 (시험용)."""
    _by_email.clear()
    _by_ip.clear()
