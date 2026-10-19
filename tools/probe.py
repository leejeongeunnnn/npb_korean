import json, requests
q = '[out:json][timeout:25];(nwr["leisure"~"pitch|stadium"](around:700,34.39183,132.48472););out geom tags;'
r = requests.post("https://overpass-api.de/api/interpreter", data={"data": q}, timeout=60, headers={"User-Agent": "npb-korean-site/1.0"})
d = r.json()
import os; os.makedirs("/tmp/pub", exist_ok=True)
json.dump(d, open("/tmp/pub/mazda.json", "w"), ensure_ascii=False)
for e in d["elements"]:
    print(e["type"], e["id"], e.get("tags"), len(e.get("geometry") or e.get("members") or []))
