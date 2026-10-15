"""동의 문구: 화면의 내장 문구(policies.js)와 서버 마이그레이션의 수정 규칙이 어긋나지 않는지, 이메일 문의(Gmail) 안내가 남지 않았는지 확인한다."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _migration():
    path = ROOT / "alembic" / "versions" / "c1e8b4a7d392_policy_v4_community_text.py"
    spec = importlib.util.spec_from_file_location("policy_edit", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fallback():
    text = (ROOT / "frontend" / "assets" / "policies.js").read_text(encoding="utf-8")
    return {p["policy_type"]: p for p in json.loads(text[text.index("["):text.rindex("]") + 1])}


def test_내장_문구에는_수정_규칙의_새_문구가_들어_있고_옛_문구는_없다():
    mig, fb = _migration(), _fallback()
    for (ptype, col), pairs in mig.EDITS.items():
        for old, new in pairs:
            assert new in fb[ptype][col], (ptype, col, new[:30])
            assert old not in fb[ptype][col], (ptype, col, old[:30])


def test_동의_문구에_이메일_문의_안내가_없다():
    for p in _fallback().values():
        for col in ("purpose_text", "collection_items", "retention_policy", "withdrawal_method", "third_party_notice"):
            assert "Gmail" not in p[col] and "이메일로 보내는 문의" not in p[col]
