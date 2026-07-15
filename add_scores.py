"""run_scoring.py가 만든 우편번호_구역평가_점수.csv를 웹앱의 data/*.json에 병합한다.
population_join.py와 같은 패턴: 각 우편번호 json 파일을 읽어서 점수 필드를 덧붙이고 다시 쓴다.

일일물량/캠프거리처럼 아직 없는 데이터가 채워져서 run_scoring.py를 다시 돌리면,
이 스크립트도 다시 실행해서 웹앱 데이터를 갱신하면 된다.
"""
import csv
import json
import os

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEBAPP_DIR, "data")
SCORE_CSV = os.path.join(WEBAPP_DIR, "..", "..", "우편번호_구역평가_점수.csv")

CATEGORY_COLUMNS = ["환경평가", "세대수평가", "접근성평가"]
RATIO_COLUMNS = {
    "아파트비율(%)": "apt",
    "오피스텔비율(%)": "officetel",
    "빌라비율(%)": "villa",
    "단독주택비율(%)": "danok",
}


def _num(v):
    if v is None or v == "":
        return None
    return round(float(v), 1)


def build_ratios(row):
    ratios = {key: _num(row.get(col)) for col, key in RATIO_COLUMNS.items()}
    known = [v for v in ratios.values() if v is not None]
    if not known:
        return ratios
    # 아파트/오피스텔/빌라/단독주택은 건물 하나당 한 카테고리로만 집계되므로(aggregate.py 참고)
    # 서로 겹치지 않는다 -> 나머지는 근린생활시설/공장/창고 등 "기타" 건물 비중
    ratios["other"] = round(max(0.0, 100.0 - sum(known)), 1)
    return ratios


def main():
    updated = 0
    missing_json = 0

    with open(SCORE_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            zipcode = row["우편번호"].strip()
            shard = zipcode[:2]
            path = os.path.join(DATA_DIR, shard, f"{zipcode}.json")
            if not os.path.exists(path):
                missing_json += 1
                continue

            excluded = set(c for c in row["제외카테고리"].split(",") if c)
            composite = row["종합점수"]

            with open(path, encoding="utf-8") as jf:
                entry = json.load(jf)

            entry["score"] = round(float(composite), 1) if composite else None
            entry["score_excluded"] = sorted(excluded)
            entry["ratios"] = build_ratios(row)

            with open(path, "w", encoding="utf-8") as jf:
                json.dump(entry, jf, ensure_ascii=False, separators=(",", ":"))
            updated += 1

    print(f"완료: {updated}개 json에 점수 반영, json 파일 없어서 건너뜀 {missing_json}건")


if __name__ == "__main__":
    main()
