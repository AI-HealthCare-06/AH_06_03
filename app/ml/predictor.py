"""예측 모델 연결 통로.
 
modeling/paeon_models.py를 불러오는 곳은 이 파일 하나뿐이다.
모델 쪽 경로나 함수 이름이 바뀌면 이 파일만 고친다. (NFR-ARCH-001, NFR-ARCH-003)
"""

import json
import sys
from pathlib import Path

# 저장소 맨 꼭대기 폴더의 위치를 계산
REPO_ROOT = Path(__file__).resolve().parents[2]
# 꼭대기 폴더 안의 modeling 폴더 위치를 계산
MODELING_DIR = REPO_ROOT / "modeling"


if str(MODELING_DIR) not in sys.path:
    sys.path.insert(0, str(MODELING_DIR))

import paeon_models

SPEC_A=json.loads(paeon_models.SPEC_A.read_text(encoding="utf-8"))
SPEC_B=json.loads(paeon_models.SPEC_B.read_text(encoding="utf-8"))

def run_model_a(user:dict) -> dict:
    """모델 A를 실행하고 결과를 반환한다"""
    return paeon_models.predict_model_a(user, spec=SPEC_A)

def run_model_b(user:dict) -> dict:
    """모델 B를 실행하고 결과를 반환한다"""
    return paeon_models.predict_model_b(user, spec=SPEC_B)