# -*- coding: utf-8 -*-
"""도도부현 경계(TopoJSON, 地球地図日本) → 간소화한 GeoJSON + 도도부현 표 생성 (1회성 도구).

  python tools/build_geo.py <japan.topojson> <prefecturalCapital.csv>

TopoJSON은 이웃 도도부현이 경계선(arc)을 공유하므로, arc 단위로 Douglas-Peucker 간소화를 하면
공유 경계가 같은 모양으로 줄어들어 틈이나 겹침이 생기지 않는다.
"""
import csv, json, math, sys, os

TOL = 0.006          # 간소화 허용 오차(도) ≈ 0.6 km
MIN_RING_PTS = 4

KO = {  # id: (한국어, 지방)
 1:("홋카이도","홋카이도"),2:("아오모리현","도호쿠"),3:("이와테현","도호쿠"),4:("미야기현","도호쿠"),5:("아키타현","도호쿠"),
 6:("야마가타현","도호쿠"),7:("후쿠시마현","도호쿠"),8:("이바라키현","간토"),9:("도치기현","간토"),10:("군마현","간토"),
 11:("사이타마현","간토"),12:("지바현","간토"),13:("도쿄도","간토"),14:("가나가와현","간토"),15:("니가타현","주부"),
 16:("도야마현","주부"),17:("이시카와현","주부"),18:("후쿠이현","주부"),19:("야마나시현","주부"),20:("나가노현","주부"),
 21:("기후현","주부"),22:("시즈오카현","주부"),23:("아이치현","주부"),24:("미에현","긴키"),25:("시가현","긴키"),
 26:("교토부","긴키"),27:("오사카부","긴키"),28:("효고현","긴키"),29:("나라현","긴키"),30:("와카야마현","긴키"),
 31:("돗토리현","주고쿠"),32:("시마네현","주고쿠"),33:("오카야마현","주고쿠"),34:("히로시마현","주고쿠"),35:("야마구치현","주고쿠"),
 36:("도쿠시마현","시코쿠"),37:("가가와현","시코쿠"),38:("에히메현","시코쿠"),39:("고치현","시코쿠"),40:("후쿠오카현","규슈·오키나와"),
 41:("사가현","규슈·오키나와"),42:("나가사키현","규슈·오키나와"),43:("구마모토현","규슈·오키나와"),44:("오이타현","규슈·오키나와"),
 45:("미야자키현","규슈·오키나와"),46:("가고시마현","규슈·오키나와"),47:("오키나와현","규슈·오키나와"),
}


def dp(points, tol):
    """Douglas-Peucker (양 끝점 유지)."""
    if len(points) < 3:
        return points
    keep = [False] * len(points); keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = points[a]; bx, by = points[b]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        best, idx = -1.0, -1
        for i in range(a + 1, b):
            px, py = points[i]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / L if L else math.hypot(px - ax, py - ay)
            if d > best:
                best, idx = d, i
        if best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(points, keep) if k]


def main(topo_path, cap_path, out_dir):
    t = json.load(open(topo_path, encoding="utf-8"))
    sx, sy = t["transform"]["scale"]; tx, ty = t["transform"]["translate"]
    arcs = []
    for arc in t["arcs"]:
        x = y = 0; pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(dp(pts, TOL))

    def ring(idx_list):
        out = []
        for i in idx_list:
            pts = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(pts if not out else pts[1:])
        return [[round(x, 3), round(y, 3)] for x, y in out]

    feats = []
    for g in list(t["objects"].values())[0]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        mp = []
        for poly in polys:
            rings = [r for r in (ring(rr) for rr in poly) if len(r) >= MIN_RING_PTS]
            if rings:
                mp.append(rings)
        pid = g["properties"]["id"]
        feats.append({"type": "Feature",
                      "properties": {"id": pid, "ja": g["properties"]["nam_ja"], "ko": KO[pid][0]},
                      "geometry": {"type": "MultiPolygon", "coordinates": mp}})
    gj = {"type": "FeatureCollection",
          "attribution": "地球地図日本 (国土地理院) / dataofjapan/land",
          "features": sorted(feats, key=lambda f: f["properties"]["id"])}
    path = os.path.join(out_dir, "prefectures.geojson")
    json.dump(gj, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("geojson", os.path.getsize(path), "bytes,", sum(len(r) for f in feats for p in f["geometry"]["coordinates"] for r in p), "points")

    table = []
    for row in csv.DictReader(open(cap_path, encoding="utf-8")):
        pid = int(row["id"]); ja = row["nam_ja"]
        short = ja if ja == "北海道" else ja[:-1]   # 静岡県 → 静岡
        table.append({"id": pid, "ja": ja, "short": short, "ko": KO[pid][0], "region": KO[pid][1],
                      "lat": round(float(row["lat"]), 4), "lon": round(float(row["lon"]), 4)})
    json.dump(table, open(os.path.join(out_dir, "prefectures.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("table", len(table))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "data/geo")
