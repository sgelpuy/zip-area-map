"""run_scoring.py가 만든 우편번호_구역평가_점수.csv를 웹앱의 data/*.json에 병합한다.
population_join.py와 같은 패턴: 각 우편번호 json 파일을 읽어서 점수 필드를 덧붙이고 다시 쓴다.

원본 데이터(면적, 인구 등)가 갱신돼서 run_scoring.py를 다시 돌리면,
이 스크립트도 다시 실행해서 웹앱 데이터를 갱신하면 된다.

**`estimated_households`를 실측세대수로 덮어쓴다**: population_join.py가 넣는 값은
행정동 세대수를 면적 비례로 나눈 추정치라, 건물 용량 비례로 배분한 추정인구와 심하게
어긋났다(세대당 인원수가 1명 미만인 구역 24.5%, 5명 초과 26.4%, 인구와 순위상관 +0.27).
건축물대장을 우편번호에 직접 집계한 실측세대수로 바꾸면 이상치가 0.6%/2.2%로 줄고
인구와의 상관이 +0.967이 된다. 단 전국 합계는 행안부 통계의 80.5% 수준으로 과소하다
(조인 실패 11.7% + 다가구주택 세대수가 대장에 0으로 기록되는 문제).
=> population_join.py를 다시 돌린 뒤에는 반드시 이 스크립트도 다시 실행할 것.
"""
import csv
import json
import os

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEBAPP_DIR, "data")
SCORE_CSV = os.path.join(WEBAPP_DIR, "..", "..", "우편번호_구역평가_점수.csv")

CATEGORY_COLUMNS = ["환경평가", "밀도평가"]
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
    # 아파트/오피스텔/빌라/단독주택 세대수만으로 분모를 잡아서(aggregate.py 참고)
    # 네 비율의 합이 항상 100%가 되도록 계산돼 있다.
    return {key: _num(row.get(col)) for col, key in RATIO_COLUMNS.items()}


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
            # 밀도 지표가 "세대당면적"에서 "1인당면적"으로 바뀌었다(인구 기반 평가로 전환).
            # 예전 필드는 의미가 달라졌으므로 남겨두지 않고 지운다.
            entry.pop("density_m2_per_household", None)
            entry["density_m2_per_person"] = _num(row.get("1인당면적(㎡)"))
            entry["estimated_population"] = _num(row.get("추정인구(명)"))
            # 면적비례 추정치를 건축물대장 실측 집계로 교체(위 docstring 참고).
            # 값이 없으면 None으로 둬서 화면에 아예 표시되지 않게 한다 - 틀린 값을
            # 보여주는 것보다 낫다.
            entry["estimated_households"] = _num(row.get("참고_실측세대수(세대)"))

            with open(path, "w", encoding="utf-8") as jf:
                json.dump(entry, jf, ensure_ascii=False, separators=(",", ":"))
            updated += 1

    print(f"완료: {updated}개 json에 점수 반영, json 파일 없어서 건너뜀 {missing_json}건")


if __name__ == "__main__":
    main()
