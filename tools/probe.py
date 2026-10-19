import json, requests, time, os
q = '[out:json][timeout:25];(nwr["leisure"~"pitch|stadium"](around:700,34.39183,132.48472););out geom tags;'
d = None
for url in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"] * 2:
    try:
        r = requests.post(url, data={"data": q}, timeout=60, headers={"User-Agent": "npb-korean-site/1.0"})
        d = r.json(); print("ok", url); break
    except Exception as e:
        print("fail", url, str(e)[:80]); time.sleep(8)
os.makedirs("/tmp/pub", exist_ok=True)
json.dump(d, open("/tmp/pub/mazda.json", "w"), ensure_ascii=False)
for e in (d or {}).get("elements", []):
    print(e["type"], e["id"], e.get("tags"), len(e.get("geometry") or e.get("members") or []))
