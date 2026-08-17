"""[주의] 지금 이 스크립트를 돌리면 인구 데이터가 절반으로 후퇴한다. 아래를 읽을 것.

`data/우편번호_추정인구.csv`의 **현행 생성기는 `scripts/build_zip_population.py`**다
(SGIS 읍면동 인구를 건물 주거용량 비율로 배분, 32,447행 / 전국 94%).
반면 이 스크립트가 읽는 `data-residents/`는 인구추정 파이프라인이 아직 45%
(15,612개)만 만들어둔 상태라, 실행하면 CSV가 그만큼으로 덮어써지고
build_zone_dataset.py -> run_scoring.py를 거치며 밀도평가가 절반 이상 구역에서 빠진다.
2026-08-17에 실제로 이 때문에 등급 컷이 겹쳐 C등급이 0개가 되는 붕괴가 있었다.
=> `data-residents/`가 전국을 커버하게 된 뒤에만 다시 쓸 것.

(이하 원래 설명)

data-residents/*/*.json(인구추정 파이프라인 10단계 산출물)에서 우편번호별
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
OUT_PATH = os.path.join(WEBAPP_DIR, "..", "..", "data", "우편번호_추정인구.csv")


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
