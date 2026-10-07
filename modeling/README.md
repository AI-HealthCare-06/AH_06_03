# modeling — PAEON 예측 모델 (모델 A · 모델 B)

담당: 김혜성 · 현재 버전: 모델 A v0.1.1 / 모델 B v0.2.0 (보정 없음)

## 먼저 읽을 것
1. `handoff/데이터_특성.md` — 모델이 말할 수 있는 것·없는 것, 팀이 결정할 것
2. `handoff/모델_연결_명세.md` — 입력·출력·변환표·적용 조건 (백엔드·프론트 연결용)
3. `handoff/생활습관_입력_가이드.md` — 흡연·음주·생활습관 설문·챌린지 구현 명세

## 구조
```text
modeling/
  paeon_models.py          추론 함수 predict_model_a / predict_model_b (전처리 포함, 표준 라이브러리만)
  model_a/                 모델 A: Framingham 10년 관상동맥질환
    train_model_a.py
    artifacts/             model_a_v0.1.1.json(서비스용 계수) · metrics · XGBoost 비교 모델
  model_b/                 모델 B: 국민건강영양조사 현재 경계군과 닮은 정도
    train_model_b.py
    artifacts/
  data_prep/
    extract_selected.py    원본 SAV → 학습용 변수 재추출
  verify_models.py         변환표·반복 일관성 검증 + handoff/test_cases.json 생성
  handoff/                 전달 문서 · demo_snippet.js · test_cases.json
```

## 서비스에서 쓰기 (데이터 필요 없음)
```python
from modeling.paeon_models import predict_model_a, predict_model_b
```
계수 파일(`model_*/artifacts/model_*_v*.json`)만 있으면 됨.

## 다시 학습하기 (데이터 필요)
데이터는 이용 조건 때문에 저장소에 없음. 로컬 데이터 폴더를 지정해서 실행:
```bash
export PAEON_DATA_DIR=/path/to/데이터   # framingham.csv, KNHANES_2022_2024_selected.parquet 가 있는 곳
python3 modeling/model_a/train_model_a.py
python3 modeling/model_b/train_model_b.py
python3 modeling/verify_models.py
```
필요 패키지: pandas, numpy, scikit-learn, xgboost, pyarrow (재추출은 pyreadstat, openpyxl)

## 데이터 출처
국민건강영양조사, 2022–2024. 질병관리청 / Kaggle Framingham Heart Study dataset — 자세한 내용은 `handoff/데이터_특성.md`

## 버전 이력
| 모델 | 버전 | 날짜 | 내용 |
|---|---|---|---|
| A | 0.1.0 | 2026-09-29 | 첫 번째 사이클 첫 버전 (로지스틱회귀, 보정 없음) |
| A | 0.1.1 | 2026-10-01 | 응답에 `vascular_age`(혈관 나이) 추가. **계수·확률은 0.1.0과 같음** |
| B | 0.1.0 | 2026-09-29 | 첫 번째 사이클 첫 버전 (로지스틱회귀, 조사구 단위 분할) |
| B | 0.2.0 | 2026-10-07 | 운동·아침 결식·외식·배달 빈도 제외 → 9개 피처. 테스트 AUC 0.745 → 0.744 (사유: `handoff/생활습관_입력_가이드.md` 부록 A) |
