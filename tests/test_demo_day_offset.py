"""DEMO_DAY_OFFSET: 서버의 오늘을 앞당긴다(팀 사전 점검용). 기본 0이면 그대로다."""
from datetime import timedelta

from app.core.config import settings
from app.core.security import utcnow
from app.services import challenge_service


def test_기본값은_0이라_오늘이_그대로다():
    assert settings.DEMO_DAY_OFFSET == 0
    assert challenge_service.today_kst() == (utcnow() + timedelta(hours=9)).date()


def test_오프셋만큼_오늘이_앞당겨진다(monkeypatch):
    base = (utcnow() + timedelta(hours=9)).date()
    monkeypatch.setattr(settings, "DEMO_DAY_OFFSET", 2)
    assert challenge_service.today_kst() == base + timedelta(days=2)
