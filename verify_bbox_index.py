"""build_bbox_index.py가 만든 bbox 인덱스 + point-in-polygon 판정을 전수 검증한다.

카카오 지도는 등록 도메인에서만 뜨기 때문에 로컬에서는 클릭을 테스트할 수 없다.
그래서 지오메트리 로직만 브라우저 밖에서 먼저 증명한다.

검증 방법: 각 구역의 "내부가 보장된 대표점"을 구해서, 브라우저와 똑같은 순서
(bbox로 후보 추림 -> ray casting -> 첫 매치)로 조회했을 때 자기 자신이 나오는지 본다.

- 대표점은 shapely representative_point()를 쓴다. centroid는 오목한 구역/구멍 있는 구역/
  MultiPolygon에서 구역 밖으로 나가버려서 쓸 수 없다.
- ray caster는 index.html의 JS를 그대로 포팅한 것을 쓴다. shapely contains로 검증하면
  JS 구현이 아니라 shapely를 검증하는 꼴이 되므로 의미가 없다.
  (대신 둘의 결과가 일치하는지를 따로 대조한다)

python -X utf8 verify_bbox_index.py
"""
import json
import os

import numpy as np
from shapely.geometry import Point, Polygon, MultiPolygon

WEBAPP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WEBAPP_DIR, "data")
INDEX_PATH = os.path.join(DATA_DIR, "bbox_index.json")


def point_in_ring(lon, lat, ring):
    """index.html의 pointInRing과 동일한 ray casting."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and \
                (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_polygons(lon, lat, polygons):
    """index.html의 pointInEntry와 동일. polygons는 [[외곽링, 구멍링, ...], ...]."""
    for rings in polygons:
        if not point_in_ring(lon, lat, rings[0]):
            continue
        in_hole = False
        for k in range(1, len(rings)):
            if point_in_ring(lon, lat, rings[k]):
                in_hole = True
                break
        if not in_hole:
            return True
    return False


def entry_polygons(entry):
    """convert.py 규약대로 [[외곽링, 구멍링, ...], ...] 형태로 통일한다."""
    if entry["type"] == "Polygon":
        return [entry["coordinates"]]
    return entry["coordinates"]


def to_shapely(polygons):
    parts = []
    for rings in polygons:
        try:
            poly = Polygon(rings[0], rings[1:])
            if not poly.is_valid:
                # 자기교차 폴리곤은 buffer(0)로 고친다. 조각이 여러 개로 갈라질 수 있다.
                poly = poly.buffer(0)
            for p in getattr(poly, "geoms", [poly]):
                if not p.is_empty and p.area > 0:
                    parts.append(p)
        except Exception:
            continue
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def main():
    with open(INDEX_PATH, encoding="utf-8") as f:
        index = json.load(f)
    print(f"인덱스 {len(index)}개 로드")

    zipcodes = [row[0] for row in index]
    bbox = np.array([row[1:] for row in index], dtype=float)  # min_lon,min_lat,max_lon,max_lat
    pos = {z: i for i, z in enumerate(zipcodes)}

    fail_missing_file = []   # 인덱스에는 있는데 data/에 파일이 없음
    fail_outside_bbox = []   # 대표점이 자기 bbox 밖 (바깥쪽 반올림 실패)
    fail_ray = []            # 포팅한 ray caster가 자기 폴리곤 밖이라고 판정
    fail_mismatch = []       # ray caster와 shapely contains 불일치
    n_hole = 0
    n_multi = 0

    points = np.full((len(index), 2), np.nan)  # lon, lat
    geoms = [None] * len(index)

    for i, zipcode in enumerate(zipcodes):
        path = os.path.join(DATA_DIR, zipcode[:2], f"{zipcode}.json")
        if not os.path.exists(path):
            fail_missing_file.append(zipcode)
            continue
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)

        polygons = entry_polygons(entry)
        if len(polygons) > 1:
            n_multi += 1
        if any(len(rings) > 1 for rings in polygons):
            n_hole += 1

        geom = to_shapely(polygons)
        if geom is None:
            fail_ray.append(zipcode)
            continue
        geoms[i] = geom

        pt = geom.representative_point()
        lon, lat = pt.x, pt.y
        points[i] = (lon, lat)

        b = bbox[i]
        if not (b[0] <= lon <= b[2] and b[1] <= lat <= b[3]):
            fail_outside_bbox.append(zipcode)

        by_ray = point_in_polygons(lon, lat, polygons)
        if not by_ray:
            fail_ray.append(zipcode)
        if by_ray != geom.contains(pt):
            fail_mismatch.append(zipcode)

        if (i + 1) % 5000 == 0:
            print(f"  {i + 1}/{len(index)} 검사 중...")

    print(f"\n구멍 있는 구역 {n_hole}개 / MultiPolygon {n_multi}개")

    # 후보 수 분포 + 겹침 검사: 각 대표점을 bbox로 조회했을 때 나오는 후보들
    print("bbox 후보 수 집계 중...")
    cand_counts = []
    overlaps = []  # (자기 우편번호, 자기 점이 안에 들어간 남의 우편번호)
    valid = ~np.isnan(points[:, 0])
    for i in np.flatnonzero(valid):
        lon, lat = points[i]
        hit = np.flatnonzero(
            (bbox[:, 0] <= lon) & (lon <= bbox[:, 2]) &
            (bbox[:, 1] <= lat) & (lat <= bbox[:, 3])
        )
        cand_counts.append(len(hit))
        pt = Point(lon, lat)
        for j in hit:
            if j == i or geoms[j] is None:
                continue
            if geoms[j].contains(pt):
                overlaps.append((zipcodes[i], zipcodes[j]))

    cand = np.array(cand_counts)
    print(f"후보 수: 평균 {cand.mean():.2f} / 중앙 {int(np.median(cand))} / "
          f"p90 {int(np.percentile(cand, 90))} / p99 {int(np.percentile(cand, 99))} / "
          f"최대 {cand.max()}")

    checked = int(valid.sum())
    n_fail = len(fail_missing_file) + len(fail_outside_bbox) + len(fail_ray) + len(fail_mismatch)
    print(f"\n=== 결과: {checked - len(set(fail_outside_bbox + fail_ray + fail_mismatch))}"
          f"/{len(index)} 통과 ===")
    print(f"  data/에 파일 없음      : {len(fail_missing_file)}건 {fail_missing_file[:5]}")
    print(f"  대표점이 bbox 밖       : {len(fail_outside_bbox)}건 {fail_outside_bbox[:5]}")
    print(f"  ray caster가 밖이라 판정: {len(fail_ray)}건 {fail_ray[:5]}")
    print(f"  shapely와 불일치       : {len(fail_mismatch)}건 {fail_mismatch[:5]}")
    print(f"  겹침(남의 구역 안에도) : {len(overlaps)}건 {overlaps[:5]}")

    if n_fail == 0 and len(overlaps) == 0:
        print("\n전부 통과. 브라우저에 넣어도 된다.")
    else:
        print("\n실패 항목이 있다. index.html에 넣기 전에 원인을 잡을 것.")


if __name__ == "__main__":
    main()
