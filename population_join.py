\
"""
읍면동(행정동) 단위 세대수 통계를 우편번호(기초구역) 구역에 면적 가중으로 배분해서
우편번호별 예상 세대수를 추정한다.

방법: 행정동 폴리곤과 우편번호 폴리곤을 원본 좌표계(EPSG:5179, 미터 단위)에서
교차시켜, 우편번호 구역이 해당 행정동과 겹치는 면적 비율만큼 그 행정동의
세대수를 나눠 갖는 것으로 계산한다 (면적 비례 배분 / areal interpolation).

전제: 행정동 내에서 세대가 균등하게 분포한다고 가정한다. 실제로는 아파트단지/
녹지 등으로 밀도가 균일하지 않으므로, 우편번호 구역이 행정동 하나를 통째로
포함하면 정확하고, 여러 행정동에 걸쳐 잘게 겹칠수록 오차가 커진다.
"""
import csv
import glob
import json
import os
import re

import shapefile
from shapely.geometry import Polygon, MultiPolygon
from shapely.strtree import STRtree

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CSV_PATH = r"C:\Users\한승우\OneDrive\Desktop\202606_202606_주민등록인구및세대현황_월간.csv"

CODE_RE = re.compile(r"\(([0-9]{10})\)\s*$")


def load_household_counts(csv_path):
    counts = {}
    with open(csv_path, encoding="cp949", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    for row in rows:
        if len(row) < 3:
            continue
        name_field = row[0].strip()
        m = CODE_RE.search(name_field)
        if not m:
            continue
        code = m.group(1)
        household_str = row[2].strip().replace(",", "")
        if not household_str.lstrip("-").isdigit():
            continue
        counts[code] = int(household_str)
    return counts


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
    household_counts = load_household_counts(CSV_PATH)
    print(f"행정동 세대수 데이터 {len(household_counts)}건 로딩")

    region_dirs = sorted(
        d for d in glob.glob(os.path.join(BASE, "구역의도형_전체분_*"))
        if os.path.isdir(d)
    )

    total_estimated = {}  # zipcode -> estimated households
    matched_dong_count = 0
    unmatched_dong_codes = set()

    for region_dir in region_dirs:
        region_name = os.path.basename(region_dir).replace("구역의도형_전체분_", "")
        for sub in sorted(os.listdir(region_dir)):
            gemd_base = os.path.join(region_dir, sub, "TL_SCCO_GEMD")
            bas_base = os.path.join(region_dir, sub, "TL_KODIS_BAS")
            if not (os.path.exists(gemd_base + ".shp") and os.path.exists(bas_base + ".shp")):
                continue

            gemd_sf = shapefile.Reader(gemd_base, encoding="cp949")
            gemd_polys = []
            gemd_households = []
            for sr in gemd_sf.iterShapeRecords():
                code = sr.record.as_dict().get("EMD_CD")
                geom = shape_to_shapely(sr.shape)
                if geom is None:
                    continue
                households = household_counts.get(code)
                if households is None:
                    unmatched_dong_codes.add(code)
                    continue
                matched_dong_count += 1
                gemd_polys.append(geom)
                gemd_households.append(households)

            if not gemd_polys:
                continue

            tree = STRtree(gemd_polys)

            bas_sf = shapefile.Reader(bas_base, encoding="cp949")
            for sr in bas_sf.iterShapeRecords():
                zipcode = sr.record.as_dict().get("BAS_ID")
                geom = shape_to_shapely(sr.shape)
                if geom is None or not geom.is_valid or geom.area == 0:
                    continue

                candidate_idxs = tree.query(geom)
                estimate = 0.0
                for idx in candidate_idxs:
                    dong_geom = gemd_polys[idx]
                    dong_households = gemd_households[idx]
                    if not geom.intersects(dong_geom):
                        continue
                    inter_area = geom.intersection(dong_geom).area
                    if inter_area <= 0:
                        continue
                    frac_of_dong = inter_area / dong_geom.area
                    estimate += frac_of_dong * dong_households

                total_estimated[zipcode] = round(estimate, 1)

            print(f"{region_name}/{sub}: 행정동 {len(gemd_polys)}개, 우편번호 {len(bas_sf)}개 처리")

    print(f"세대수 매칭된 행정동: {matched_dong_count}, 매칭 안 된 코드: {len(unmatched_dong_codes)}")
    print(f"추정치 계산된 우편번호: {len(total_estimated)}")

    # merge into existing per-zipcode json files
    updated = 0
    for zipcode, estimate in total_estimated.items():
        shard = zipcode[:2]
        path = os.path.join(DATA_DIR, shard, f"{zipcode}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
        entry["estimated_households"] = estimate
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, separators=(",", ":"))
        updated += 1

    print(f"data/*.json {updated}개 파일에 estimated_households 필드 추가")


if __name__ == "__main__":
    main()
