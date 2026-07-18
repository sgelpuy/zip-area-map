\
"""
우편번호(기초구역, TL_KODIS_BAS) 폴리곤의 실제 면적(m^2)을 계산해서
data/*/*.json 각 항목에 area_m2 필드로 채워 넣는다.

원본 좌표계(EPSG:5179, Korea 2000 / Unified CS)는 미터 단위 평면좌표라
좌표 그대로 shapely Polygon.area를 쓰면 곧바로 m^2가 나온다
(convert.py가 만드는 data/*.json은 WGS84로 재투영된 좌표라 면적 계산에는
 쓰지 않는다).
"""
import glob
import json
import os

import shapefile
from shapely.geometry import Polygon, MultiPolygon

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def shape_to_shapely(shp):
    parts = list(shp.parts) + [len(shp.points)]
    rings = [shp.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]

    def signed_area(ring):
        s = 0.0
        for i in range(len(ring) - 1):
            x1, y1 = ring[i]
            x2, y2 = ring[i + 1]
            s += x1 * y2 - x2 * y1
        return s / 2.0

    polygons = []
    for ring in rings:
        if len(ring) < 4:
            continue
        if signed_area(ring) < 0:
            polygons.append([ring])
        else:
            if polygons:
                polygons[-1].append(ring)
            else:
                polygons.append([ring])

    polys = []
    for rings_group in polygons:
        try:
            poly = Polygon(rings_group[0], rings_group[1:])
            if poly.is_valid and poly.area > 0:
                polys.append(poly)
        except Exception:
            continue

    if not polys:
        return None
    if len(polys) == 1:
        return polys[0]
    return MultiPolygon(polys)


def main():
    region_dirs = sorted(
        d for d in glob.glob(os.path.join(BASE, "구역의도형_전체분_*"))
        if os.path.isdir(d)
    )

    areas = {}  # zipcode -> area_m2
    for region_dir in region_dirs:
        region_name = os.path.basename(region_dir).replace("구역의도형_전체분_", "")
        for sub in sorted(os.listdir(region_dir)):
            bas_base = os.path.join(region_dir, sub, "TL_KODIS_BAS")
            if not os.path.exists(bas_base + ".shp"):
                continue

            bas_sf = shapefile.Reader(bas_base, encoding="cp949")
            count = 0
            for sr in bas_sf.iterShapeRecords():
                zipcode = sr.record.as_dict().get("BAS_ID")
                geom = shape_to_shapely(sr.shape)
                if geom is None or not geom.is_valid or geom.area == 0:
                    continue
                areas[zipcode] = round(geom.area, 1)
                count += 1
            print(f"{region_name}/{sub}: {count}개 면적 계산")

    print(f"총 {len(areas)}개 우편번호 면적 계산 완료")

    updated = 0
    for zipcode, area_m2 in areas.items():
        shard = zipcode[:2]
        path = os.path.join(DATA_DIR, shard, f"{zipcode}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        entry["area_m2"] = area_m2
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, separators=(",", ":"))
        updated += 1

    print(f"data/*.json {updated}개 파일에 area_m2 필드 추가")


if __name__ == "__main__":
    main()
