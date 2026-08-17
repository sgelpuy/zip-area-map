"""data/*/*.json 각 우편번호 구역의 bbox(경계 사각형)를 모아 data/bbox_index.json을 만든다.

웹앱에서 "지도를 클릭한 좌표가 어느 우편번호인가"를 알아내기 위한 인덱스다.
폴리곤 전체는 34,516개 파일 145MB라 브라우저가 통째로 받을 수 없지만,
bbox만 모으면 1.5MB라 한 번에 받아서 후보를 걸러낼 수 있다.
(클릭 → bbox로 후보 1~7개 추림 → 그 후보들의 폴리곤 json만 받아서 point-in-polygon 판정)

원본 shapefile이 아니라 이미 만들어진 data/*.json을 읽는다. 인덱스가 걸러야 하는 대상이
바로 그 json 파일들이라, 브라우저가 실제로 받는 좌표와 100% 같은 값이 들어가야 하기 때문이다
(add_scores.py와 같은 순회 패턴).

convert.py를 다시 돌려서 data/가 갱신되면 이 스크립트도 반드시 다시 돌려야 한다.
인덱스가 낡으면 (a) 삭제된 구역을 fetch해 404가 나거나 (b) 새로 생긴 구역이 클릭에 안 잡힌다.
둘 다 에러 없이 "구역 없음"으로만 보여서 원인 파악이 어렵다.
"""
import json
import math
import os

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEBAPP_DIR, "data")
INDEX_PATH = os.path.join(DATA_DIR, "bbox_index.json")
ROUND_DIGITS = 4  # 약 11m. bbox는 후보를 거르는 용도라 이 정도면 충분하다


def entry_bbox(entry):
    """[min_lon, min_lat, max_lon, max_lat]. 좌표를 못 찾으면 None.

    구멍(hole) 링은 외곽 링 안에 있으므로 bbox에 영향이 없다.
    Polygon/MultiPolygon을 구분하지 않고 모든 링의 모든 점을 훑으면 된다.
    """
    min_lon = min_lat = math.inf
    max_lon = max_lat = -math.inf

    stack = [entry.get("coordinates")]
    while stack:
        node = stack.pop()
        if not isinstance(node, list) or not node:
            continue
        # 좌표점([lon, lat])이면 갱신, 아니면 한 겹 더 들어간다
        if isinstance(node[0], (int, float)):
            lon, lat = node[0], node[1]
            min_lon = min(min_lon, lon)
            min_lat = min(min_lat, lat)
            max_lon = max(max_lon, lon)
            max_lat = max(max_lat, lat)
        else:
            stack.extend(node)

    if math.isinf(min_lon):
        return None

    # 반드시 바깥쪽으로 반올림한다. round()를 쓰면 bbox가 실제 폴리곤보다 작아질 수 있고,
    # 그러면 구역 가장자리를 클릭했을 때 자기 구역이 후보에서 빠져 "구역 없음"이 뜬다.
    scale = 10 ** ROUND_DIGITS
    return [
        math.floor(min_lon * scale) / scale,
        math.floor(min_lat * scale) / scale,
        math.ceil(max_lon * scale) / scale,
        math.ceil(max_lat * scale) / scale,
    ]


def main():
    rows = []
    skipped = 0

    for shard in sorted(os.listdir(DATA_DIR)):
        shard_dir = os.path.join(DATA_DIR, shard)
        if not os.path.isdir(shard_dir):
            continue

        count = 0
        for name in sorted(os.listdir(shard_dir)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(shard_dir, name), encoding="utf-8") as f:
                entry = json.load(f)

            bbox = entry_bbox(entry)
            if bbox is None:
                skipped += 1
                continue
            rows.append([entry["zipcode"]] + bbox)
            count += 1

        print(f"{shard}: {count}개")

    # 우편번호 오름차순으로 정렬해두면 재생성해도 git diff가 안정적이다
    rows.sort(key=lambda r: r[0])

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))

    size_mb = os.path.getsize(INDEX_PATH) / 1024 / 1024
    print(f"완료: {len(rows)}개 구역 bbox 저장 ({size_mb:.2f}MB), 좌표 없어서 건너뜀 {skipped}건")


if __name__ == "__main__":
    main()
