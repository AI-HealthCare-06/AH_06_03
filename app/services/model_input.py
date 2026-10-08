"""DB에 저장된 값 → 모델 입력(모델_연결_명세 §1)으로 번역한다."""
from datetime import date

# 📦 건강기록 번역표: DB 지표 이름 → 모델 이름
METRIC_TO_MODEL = {
    "SBP": "sbp", "DBP": "dbp", "HEIGHT": "height_cm", "WEIGHT": "weight_kg", "WAIST": "waist_cm",
    "TOTAL_CHOL": "total_chol", "HDL": "hdl", "FASTING_GLUCOSE": "fasting_glucose",
    "SMOKING": "smoking", "DIABETES": "diabetes", "HTN_STATUS": "htn_status",
    "PARENT_HTN": "parent_htn", "ALCOHOL_FREQ": "drink_freq", "ALCOHOL_AMOUNT": "drink_amount",
}



def age_on(birth_date: date, on: date) -> int:
    """그날 기준 만 나이."""
    return on.year - birth_date.year - ((on.month, on.day) < (birth_date.month, birth_date.day))


def build_model_input(sex: str, birth_date: date, examination_date: date, measurements: list[dict]) -> dict:
    """measurements: [{"metric_code", "value_num", "value_code"}...]
    모델 입력은 W04 건강정보만 쓴다. 설문은 챌린지 판정 전용 (생활습관 구현 명세 §0)."""
    user = {
        "age": age_on(birth_date, examination_date),
        "sex": "M" if sex == "male" else "F",
    }
    for m in measurements:
        key = METRIC_TO_MODEL.get(m["metric_code"])
        if key is None:
            continue  # BMI, ECIG처럼 모델에 안 보내는 값은 건너뜀
        value = m["value_num"] if m["value_num"] is not None else m["value_code"]
        if key == "diabetes":
            value = value == "true"
        user[key] = value
    return user