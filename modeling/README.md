# modeling — PAEON 예측 모델 (모델 A · 모델 B)

담당: 김혜성 · 현재 버전: **모델 A v0.2.0 (한국인 보정, 2026-10-20)** / 모델 B v0.2.0

## 먼저 읽을 것
1. `handoff/데이터_특성.md` — 모델이 말할 수 있는 것·없는 것, 팀이 결정할 것
2. `handoff/모델_연결_명세.md` — 입력·출력·변환표·적용 조건 (백엔드·프론트 연결용)
3. `handoff/생활습관_입력_가이드.md` — 흡연·음주·생활습관 설문·챌린지 구현 명세

## 모델 A v0.2.0 업그레이드 — 역할별로 볼 문서 (2026-10-20)
변경: 확률을 한국인 기준으로 재보정, 범주 기준을 확률 <2% / 2~9% / ≥9%로 변경, `percentile`(같은 성별·연령대 상위 %) 채움, 혈관 나이 기준을 한국 성인 평균으로 변경, `sex` 필수.

| 역할 | 볼 문서 | 볼 곳 |
|---|---|---|
| 전원 (무엇이 바뀌었나) | `handoff/모델_연결_명세.md` | 맨 위 "모델 A v0.2.0 변경 요약" — 항목별 이전 → 현재 → 담당 할 일 |
| 백엔드 | `handoff/모델_연결_명세.md` | §2.1 (`sex` 필수), §3 출력, §4 기대값(`test_cases.json`), §8 전·후 비교 / `app/ml/predictor.py`는 코드 변경 없음 |
| 프론트 | `handoff/모델_연결_명세.md` §3 · `handoff/데이터_특성.md` §1.1 | 확률 % 표시 규칙, 금지 표현, 화면 안내 문구, `percentile` 표기 |
| 배포 | 이 README "서비스에서 쓰기" | `modeling/` 파일만 바뀜. DB 스키마·환경변수·의존성 변경 없음 |
| 근거·한계·다음 버전 | `handoff/데이터_특성.md` §1.6 · §1.7 · §1.8 | 보정 방법과 논문 대조, 범주 기준 근거, 한계, 다음 버전 과제 |
| 결정 기록 | `docs/모델_개발_계획_고혈압.md` | 정정 대비표 2026-10-20 (이전 → 현재 → 영향 파트) |

## 구조
```text
modeling/
  paeon_models.py          추론 함수 predict_model_a / predict_model_b (전처리 포함, 표준 라이브러리만)
  model_a/                 모델 A: Framingham 10년 관상동맥질환
    train_model_a.py
    build_model_a_v020.py  v0.2.0 생성 (KNHANES 필요, 저장소 밖 데이터)
    artifacts/             model_a_v0.2.0.json(서비스용) · model_a_v0.1.1.json(이전) · metrics · XGBoost 비교 모델
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
python3 modeling/model_a/build_model_a_v020.py   # 모델 A v0.2.0 (v0.1.1 계수 + KNHANES)
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
| A | 0.2.0 | 2026-10-20 | **계수는 0.1.1과 같음.** 성별 절편 재보정(한국 평균 프로필 10년 위험 남 1.03% · 여 0.40%, Jee 2014), 범주 확률 <2% / 2~9% / ≥9%(JAS 2017), `percentile` 채움, 혈관 나이 기준 = 한국 성인 평균, `sex` 필수. 한국인 결과 자료로 검증하지 않음 — 한계·다음 버전: `handoff/데이터_특성.md` §1.8 |
| B | 0.1.0 | 2026-09-29 | 첫 번째 사이클 첫 버전 (로지스틱회귀, 조사구 단위 분할) |
| B | 0.2.0 | 2026-10-07 | 운동·아침 결식·외식·배달 빈도 제외 → 9개 피처. 테스트 AUC 0.745 → 0.744 (사유: `handoff/생활습관_입력_가이드.md` 부록 A) |
