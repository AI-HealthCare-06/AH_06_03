"""예측 모델 연결 통로.
 
modeling/paeon_models.py를 불러오는 곳은 이 파일 하나뿐이다.
모델 쪽 경로나 함수 이름이 바뀌면 이 파일만 고친다. (NFR-ARCH-001, NFR-ARCH-003)
"""

import json
import sys
from pathlib import Path
from datetime import date

# 저장소 맨 꼭대기 폴더의 위치를 계산
REPO_ROOT = Path(__file__).resolve().parents[2]
# 꼭대기 폴더 안의 modeling 폴더 위치를 계산
MODELING_DIR = REPO_ROOT / "modeling"


if str(MODELING_DIR) not in sys.path:
    sys.path.insert(0, str(MODELING_DIR))

import paeon_models

MODEL_ARTIFACTS = {
    "MODEL_A": {
        "0.1.1": MODELING_DIR / "model_a" / "artifacts" / "model_a_v0.1.1.json",
        "0.2.0": MODELING_DIR / "model_a" / "artifacts" / "model_a_v0.2.0.json",
    },
    "MODEL_B": {
        "0.1.0": MODELING_DIR / "model_b" / "artifacts" / "model_b_v0.1.0.json",
        "0.2.0": MODELING_DIR / "model_b" / "artifacts" / "model_b_v0.2.0.json",
    },
}

MODEL_SPECS = {
    model_code: {
        version: json.loads(path.read_text(encoding="utf-8"))
        for version, path in versions.items()
    }
    for model_code, versions in MODEL_ARTIFACTS.items()
}

CURRENT_VERSION = {
    "MODEL_A": "0.2.0",
    "MODEL_B": "0.2.0",
}

MODEL_RELEASE_INFO = {
    "MODEL_A": {
        "0.2.0": {
            "updated_on": date(2026, 10, 20),
            "change_note": "한국인 보정 확률 기준",
        },
    },
    "MODEL_B": {
        "0.2.0": {
            "updated_on": date(2026, 10, 20),
            "change_note": "생활습관·체형 비교 기준 업데이트",
        },
    },
}

def model_release_info(model_code: str, version: str | None) -> dict:
    """모델 코드·버전에 맞는 배포 안내 정보. 모르면 빈값."""
    if version is None:
        return {}

    return MODEL_RELEASE_INFO.get(model_code, {}).get(version, {})


def current_program_model_info() -> dict:
    """새 12주 프로그램을 시작할 때 저장할 최신 모델 정보."""
    model_a_version = CURRENT_VERSION["MODEL_A"]
    model_b_version = CURRENT_VERSION["MODEL_B"]
    model_a_info = MODEL_RELEASE_INFO["MODEL_A"].get(model_a_version, {})

    return {
        "model_a_version": model_a_version,
        "model_b_version": model_b_version,
        # 프론트 status.model_version은 대표값으로 모델 A 버전을 사용한다.
        "model_version": model_a_version,
        "model_updated_on": model_a_info.get("updated_on"),
        "change_note": model_a_info.get("change_note"),
    }

SPEC_A = MODEL_SPECS["MODEL_A"][CURRENT_VERSION["MODEL_A"]]
SPEC_B = MODEL_SPECS["MODEL_B"][CURRENT_VERSION["MODEL_B"]]


def get_model_spec(model_code: str, version: str | None = None) -> dict:
    """요청한 버전의 저장된 모델 JSON을 돌려준다. 버전을 생략하면 최신 버전이다."""
    selected_version = version or CURRENT_VERSION[model_code]
    try:
        return MODEL_SPECS[model_code][selected_version]
    except KeyError as e:
        raise ValueError(f"지원하지 않는 {model_code} 모델 버전입니다: {selected_version}") from e


def run_model_a(user: dict, version: str | None = None) -> dict:
    return paeon_models.predict_model_a(
        user,
        spec=get_model_spec("MODEL_A", version),
    )


def run_model_b(user: dict, version: str | None = None) -> dict:
    return paeon_models.predict_model_b(
        user,
        spec=get_model_spec("MODEL_B", version),
    )

def similarity_level_b(score: float | None, model_version: str | None) -> str | None:
    """저장된 모델 B 버전의 기준값으로 닮은 정도를 계산한다."""
    if score is None or model_version is None:
        return None

    try:
        spec = get_model_spec("MODEL_B", model_version)
    except ValueError:
        return None

    return paeon_models.similarity_level_b(score, spec)