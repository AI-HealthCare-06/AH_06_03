"""비밀 열쇠가 기본값이면 서버가 켜지지 않는다."""
from types import SimpleNamespace

import pytest

from app.core.config import DEFAULT_JWT_SECRET, check_required_secrets


@pytest.mark.parametrize("value", ["", DEFAULT_JWT_SECRET])
def test_기본값이나_빈_값이면_멈춘다(value):
    with pytest.raises(RuntimeError):
        check_required_secrets(SimpleNamespace(JWT_SECRET=value))


def test_따로_넣은_값이면_통과한다():
    check_required_secrets(SimpleNamespace(JWT_SECRET="a-long-random-value-from-env-0123456789"))