"""서버가 남기는 관리자 행위마다 기록 화면(admin.html)에 한글 이름표가 있는지 확인한다.
이름표가 빠지면 기록 화면에 영어 이름(notice_create 등)이 그대로 보인다."""
import re
from pathlib import Path

from app.services.admin_registry_service import GRANT, REVOKE

ROOT = Path(__file__).resolve().parents[1]
RECORD_CALL = re.compile(r'audit_service\.record\(\s*[^,]+,\s*[^,]+,\s*"([a-z_]+)"')


def server_actions() -> set[str]:
    found = {GRANT, REVOKE}
    for path in (ROOT / "app").rglob("*.py"):
        found |= set(RECORD_CALL.findall(path.read_text(encoding="utf-8")))
    return found


def screen_labels() -> set[str]:
    html = (ROOT / "frontend" / "admin.html").read_text(encoding="utf-8")
    body = re.search(r"const ACTION_LABEL = \{(.*?)\};", html, re.S).group(1)
    return set(re.findall(r"([a-z_]+):\s*'", body))


def test_every_admin_action_has_label():
    actions = server_actions()
    assert len(actions) >= 20                       # 찾는 방식이 깨져 아무것도 못 찾는 경우를 막는다
    assert actions - screen_labels() == set()
