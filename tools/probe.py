import json, requests, time, os, math
S = {"tokyodome": (35.70562, 139.75191), "koshien": (34.72121, 135.36162), "vantelin": (35.18595, 136.94745),
     "yokohama": (35.44332, 139.6401), "jingu": (35.67437, 139.71708), "mazda": (34.39183, 132.48472),
     "paypay": (33.59539, 130.36223), "kyocera": (34.66924, 135.47615), "zozo": (35.64513, 140.03079),
     "rakuten": (38.25656, 140.90253), "belluna": (35.76861, 139.42052), "escon": (42.99042, 141.55442)}
MAIN = {"東京": (35.6812, 139.7671), "大阪": (34.7025, 135.4959), "名古屋": (35.1709, 136.8815), "横浜": (35.4658, 139.6223),
        "広島": (34.3976, 132.4753), "博多": (33.5897, 130.4207), "仙台": (38.2601, 140.8824), "札幌": (43.0687, 141.3508),
        "池袋": (35.7295, 139.7109), "渋谷": (35.6580, 139.7016), "梅田": (34.7050, 135.4983), "難波": (34.6666, 135.5011)}
def hav(a, b):
    R=6371000; p1,p2=math.radians(a[0]),math.radians(b[0]); dp=p2-p1; dl=math.radians(b[1]-a[1])
    return 2*R*math.asin(math.sqrt(math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2))
def ov(q):
    for url in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"] * 3:
        try:
            r = requests.post(url, data={"data": q}, timeout=90, headers={"User-Agent": "npb-korean-site/1.0"})
            return r.json()
        except Exception as e:
            print("retry", url, str(e)[:60]); time.sleep(10)
    return {"elements": []}
out = {}
for k, (la, lo) in S.items():
    d = ov(f'[out:json][timeout:60];(node["railway"="station"](around:2500,{la},{lo});node["public_transport"="station"]["train"="yes"](around:2500,{la},{lo}););out body;')
    seen = {}
    for e in d["elements"]:
        t = e.get("tags", {}); nm = t.get("name")
        if "lat" not in e: continue
        if not nm: continue
        dist = hav((la, lo), (e["lat"], e["lon"]))
        if nm not in seen or dist < seen[nm]["dist"]:
            seen[nm] = {"name": nm, "en": t.get("name:en", ""), "ko": t.get("name:ko", ""), "lat": e["lat"], "lon": e["lon"],
                        "dist": round(dist), "operator": t.get("operator", ""), "line": t.get("line", "") or t.get("network", "")}
    out[k] = sorted(seen.values(), key=lambda x: x["dist"])[:8]
    print(k, [(s["name"], s["dist"], s["operator"]) for s in out[k]])
    time.sleep(3)
os.makedirs("/tmp/pub", exist_ok=True)
json.dump(out, open("/tmp/pub/stations.json", "w"), ensure_ascii=False, indent=1)
