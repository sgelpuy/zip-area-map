\
import glob
import json
import os

import shapefile
from pyproj import Transformer

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
INDEX_PATH = os.path.join(DATA_DIR, "index.json")
ROUND_DIGITS = 6  # ~0.11m precision, plenty for this use case

# 우정사업본부 TL_KODIS_BAS shapefiles are distributed in EPSG:5179 (Korea 2000 / Unified CS)
transformer = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)


def shape_to_geojson_coords(shp):
    """Convert a pyshp polygon shape (possibly multi-ring) into GeoJSON
    Polygon/MultiPolygon coordinates, reprojected to lon/lat, honoring
    shapefile ring winding order (clockwise = outer, ccw = hole)."""
    parts = list(shp.parts) + [len(shp.points)]
    rings = []
    for i in range(len(parts) - 1):
        pts = shp.points[parts[i]:parts[i + 1]]
        ring = [
            [round(lon, ROUND_DIGITS), round(lat, ROUND_DIGITS)]
            for lon, lat in (transformer.transform(x, y) for x, y in pts)
        ]
        rings.append(ring)

    def signed_area(ring):
        s = 0.0
        for i in range(len(ring) - 1):
            x1, y1 = ring[i]
            x2, y2 = ring[i + 1]
            s += x1 * y2 - x2 * y1
        return s / 2.0

    polygons = []  # each: [outer, hole, hole, ...]
    for ring in rings:
        if signed_area(ring) < 0:  # clockwise -> new outer ring
            polygons.append([ring])
        else:  # ccw -> hole, belongs to last outer ring
            if polygons:
                polygons[-1].append(ring)
            else:
                polygons.append([ring])

    if len(polygons) == 1:
        return "Polygon", polygons[0]
    return "MultiPolygon", polygons


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    index = {}  # zipcode -> region name, used for fast "not found" checks client-side
    region_dirs = sorted(
        d for d in glob.glob(os.path.join(BASE, "구역의도형_전체분_*"))
        if os.path.isdir(d)
    )
    for region_dir in region_dirs:
        region_name = os.path.basename(region_dir).replace("구역의도형_전체분_", "")
        for sub in sorted(os.listdir(region_dir)):
            shp_base = os.path.join(region_dir, sub, "TL_KODIS_BAS")
            if not os.path.exists(shp_base + ".shp"):
                continue
            sf = shapefile.Reader(shp_base, encoding="cp949")
            count = 0
            for sr in sf.iterShapeRecords():
                rec = sr.record.as_dict()
                shp = sr.shape
                zipcode = rec["BAS_ID"]
                if not shp.points:
                    continue
                gtype, coords = shape_to_geojson_coords(shp)
                entry = {
                    "zipcode": zipcode,
                    "region": region_name,
                    "type": gtype,
                    "coordinates": coords,
                }
                shard = zipcode[:2]
                shard_dir = os.path.join(DATA_DIR, shard)
                os.makedirs(shard_dir, exist_ok=True)
                with open(os.path.join(shard_dir, f"{zipcode}.json"), "w", encoding="utf-8") as f:
                    json.dump(entry, f, ensure_ascii=False, separators=(",", ":"))
                index[zipcode] = region_name
                count += 1
            print(f"{region_name}/{sub}: {count} records processed")

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Total zipcodes: {len(index)}")
    print(f"Written per-zipcode files under {DATA_DIR}")


if __name__ == "__main__":
    main()
