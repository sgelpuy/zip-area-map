"""data/*/*.json에 있는 우편번호별 면적(area_m2)을 프로젝트 루트의 CSV로 뽑아낸다.
build_zone_dataset.py가 이 CSV를 읽어서 '면적(㎡)' 변수를 채운다.
compute_area.py로 면적이 갱신되면 이 스크립트도 다시 돌려야 한다.
"""
import csv
import glob
import json
import os

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEBAPP_DIR, "data")
OUT_PATH = os.path.join(WEBAPP_DIR, "..", "..", "우편번호_면적.csv")


def main():
    rows = []
    for path in glob.glob(os.path.join(DATA_DIR, "*", "*.json")):
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        area = entry.get("area_m2")
        if area is not None:
            rows.append((entry["zipcode"], area))

    rows.sort()
    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["우편번호", "면적_m2"])
        w.writerows(rows)

    print(f"완료: {OUT_PATH} ({len(rows)}행)")


if __name__ == "__main__":
    main()
