"""[주의] add_scores.py를 돌린 뒤에 이걸 실행하면 값의 의미가 뒤바뀐다.

이 스크립트가 읽는 `data/*.json`의 `estimated_households`는 add_scores.py가
**건축물대장 실측세대수로 덮어쓴다**(면적비례 추정치가 인구와 심하게 어긋나서 내린 결정).
그 상태에서 실행하면 "행안부 면적비례 추정치"여야 할 `우편번호_예상세대수.csv`가
실측세대수로 바뀌고, build_zone_dataset.py가 이를 `참고_예상세대수_행안부` 컬럼에
넣어 `참고_실측세대수`와 똑같은 값이 된다(두 추정치를 비교하려던 목적이 사라진다).
종합점수는 둘 다 참고 컬럼이라 영향받지 않는다.
=> population_join.py로 면적비례 세대수를 다시 채운 직후에만 쓸 것.

(이하 원래 설명)

data/*/*.json에 있는 우편번호별 예상세대수(estimated_households)를
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
OUT_PATH = os.path.join(WEBAPP_DIR, "..", "..", "data", "우편번호_예상세대수.csv")


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
