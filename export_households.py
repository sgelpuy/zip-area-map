"""data/*/*.json에 있는 우편번호별 예상세대수(estimated_households)를
프로젝트 루트의 CSV로 뽑아낸다. build_zone_dataset.py가 이 CSV를 읽어서
'예상세대수(세대)' 변수를 채운다. population_join.py로 세대수 추정치가
갱신되면 이 스크립트도 다시 돌려야 한다.
"""
import csv
import glob
import json
import os

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEBAPP_DIR, "data")
OUT_PATH = os.path.join(WEBAPP_DIR, "..", "..", "우편번호_예상세대수.csv")


def main():
    rows = []
    for path in glob.glob(os.path.join(DATA_DIR, "*", "*.json")):
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        hh = entry.get("estimated_households")
        if hh is not None:
            rows.append((entry["zipcode"], hh))

    rows.sort()
    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["우편번호", "예상세대수"])
        w.writerows(rows)

    print(f"완료: {OUT_PATH} ({len(rows)}행)")


if __name__ == "__main__":
    main()
