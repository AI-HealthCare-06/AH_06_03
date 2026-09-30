"""변수 선정표(후보 선정표 시트)의 변수로 KNHANES 2022–2024 원본 SAV 재추출.

입력: $PAEON_DATA_DIR/국민건강영양조사/HN22~24_ALL.sav, $PAEON_DATA_DIR/변수선정/KNHANES_변수선정표.xlsx
출력: $PAEON_DATA_DIR/KNHANES_2022_2024_selected.csv / .parquet  (기존 21열 병합 파일은 건드리지 않음)
원시자료는 질병관리청 누리집에서 서약 후 내려받음 (저장소에 올리지 않음)
  - 후보 선정표의 모든 변수(판정 무관, 46개 중 존재하는 것) + year
  - 값은 원본 코드 그대로 (8·9 등 정제는 모델 학습 스크립트에서)
"""
from pathlib import Path
import os
import pandas as pd
import pyreadstat

BASE = Path(os.environ.get("PAEON_DATA_DIR", Path(__file__).resolve().parents[3] / "데이터"))
SAV = {y: BASE / "국민건강영양조사" / f"HN{y[2:]}_ALL.sav" for y in ["2022", "2023", "2024"]}
TABLE = BASE / "변수선정" / "KNHANES_변수선정표.xlsx"
OUT = BASE / "KNHANES_2022_2024_selected"


def main():
    short = pd.read_excel(TABLE, sheet_name="후보 선정표")
    wanted = list(dict.fromkeys(short["변수"]))
    frames = []
    for y, path in SAV.items():
        _, meta = pyreadstat.read_sav(path, metadataonly=True)
        cols = [v for v in wanted if v in meta.column_names]
        missing = sorted(set(wanted) - set(cols))
        df, _ = pyreadstat.read_sav(path, usecols=cols)
        df.insert(1, "year", int(y))
        frames.append(df)
        print(y, df.shape, "없는 변수:", missing or "-")
    data = pd.concat(frames, ignore_index=True)
    data.to_csv(OUT.with_suffix(".csv"), index=False)
    data.to_parquet(OUT.with_suffix(".parquet"), index=False)
    train = data[(data["age"] >= 19) & data["HE_HP"].isin([1, 2, 3])]
    print("저장:", OUT.with_suffix(".csv"), data.shape, "| 모델 B 학습 대상", len(train),
          "경계군", int(train["HE_HP"].isin([2, 3]).sum()))


if __name__ == "__main__":
    main()
