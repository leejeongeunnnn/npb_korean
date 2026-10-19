"""구장 방위(홈→센터) 추정용: OSM 야구장 폴리곤을 받아 그림과 후보 방위를 저장."""
import json, math, os, time, requests
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
OUT = "/tmp/pub"; os.makedirs(OUT, exist_ok=True)
S = {"koshien": (34.72121, 135.36162), "yokohama": (35.44332, 139.6401), "jingu": (35.67437, 139.71708),
     "mazda": (34.39183, 132.48472), "zozo": (35.64513, 140.03079), "rakuten": (38.25656, 140.90253),
     "escon": (42.99042, 141.55442), "tokyodome": (35.70562, 139.75191), "vantelin": (35.18595, 136.94745),
     "kyocera": (34.66924, 135.47615), "paypay": (33.59539, 130.36223), "belluna": (35.76861, 139.42052)}
res = {}
for k, (la, lo) in S.items():
    q = f'[out:json][timeout:25];(way["leisure"="pitch"](around:450,{la},{lo});way["leisure"="stadium"](around:450,{la},{lo});node["playing_field"](around:450,{la},{lo}););out geom tags;'
    for i in range(3):
        try:
            r = requests.post("https://overpass-api.de/api/interpreter", data={"data": q}, timeout=60,
                              headers={"User-Agent": "npb-korean-site/1.0 (github.com/leejeongeunnnn/npb_korean)"})
            d = r.json(); break
        except Exception as e:
            print(k, "retry", e); time.sleep(5); d = {"elements": []}
    els = [e for e in d.get("elements", []) if e.get("geometry")]
    res[k] = [{"id": e["id"], "tags": e.get("tags", {}), "geom": [[p["lat"], p["lon"]] for p in e["geometry"]]} for e in els]
    fig, ax = plt.subplots(figsize=(6, 6))
    for e in res[k]:
        xs = [p[1] for p in e["geom"]]; ys = [p[0] for p in e["geom"]]
        t = e["tags"]; lab = f'{t.get("leisure")}/{t.get("sport","")}/{t.get("surface","")} {e["id"]}'
        ax.plot(xs, ys, lw=2 if t.get("sport", "").find("baseball") >= 0 else 0.8, label=lab[:50])
    ax.plot([lo], [la], "k+", ms=12)
    ax.set_aspect(1 / math.cos(math.radians(la)))
    ax.legend(fontsize=6, loc="lower left"); ax.set_title(k)
    fig.savefig(f"{OUT}/{k}.png", dpi=90); plt.close(fig)
    print(k, len(res[k]), [ (e["tags"].get("leisure"), e["tags"].get("sport"), len(e["geom"])) for e in res[k]])
    time.sleep(2)
json.dump(res, open(f"{OUT}/osm.json", "w"), ensure_ascii=False)
