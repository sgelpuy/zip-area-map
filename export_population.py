"""data-residents/*/*.json(인구추정 파이프라인 10단계 산출물)에서 우편번호별
추정 거주인구를 프로젝트 루트의 CSV로 뽑아낸다.
build_zone_dataset.py가 이 CSV를 읽어서 '추정인구(명)' 변수를 채운다.

export_households.py(세대수)와 같은 패턴이지만 읽는 디렉토리가 다르다:
  - export_households.py -> data/           (폴리곤 + 면적비례 배분 세대수)
  - 이 스크립트          -> data-residents/ (인구추정 파이프라인 산출물)

status가 ok가 아닌 구역(data_unavailable)은 값을 비워 둔다 - 다운스트림에서
밀도평가가 자동으로 제외되게 하려는 것이고, 0으로 채우면 안 된다.
"""
import csv
import glob
import json
import os

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
RESIDENTS_DIR = os.path.join(WEBAPP_DIR, "data-residents")
OUT_PATH = os.path.join(WEBAPP_DIR, "..", "..", "우편번호_추정인구.csv")


def main():
    rows = []
    n_unavailable = 0
    for path in glob.glob(os.path.join(RESIDENTS_DIR, "*", "*.json")):
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        zipcode = entry.get("postal_code")
        if not zipcode:
            continue
        total = entry.get("total") or {}
        residents = total.get("estimated_residents")
        households = total.get("estimated_households")
        if entry.get("status") != "ok" or residents is None:
            n_unavailable += 1
            rows.append((zipcode, "", ""))
            continue
        rows.append((zipcode, residents, households if households is not None else ""))

    rows.sort()
    with open(OUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["우편번호", "추정인구", "추정가구수"])
        w.writerows(rows)

    print(f"완료: {os.path.abspath(OUT_PATH)} ({len(rows)}행)")
    print(f"  인구값 있음: {len(rows) - n_unavailable:,}행 / 값 없음(data_unavailable): {n_unavailable:,}행")


if __name__ == "__main__":
    main()
