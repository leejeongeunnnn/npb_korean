import json, os, sys, shutil
sys.path.insert(0, os.getcwd())
import collect as C, collect_games as G
games = C.fetch_games_by_date("2026-10-05")
print("SCHEDULE gids:", [(g["away"], g["home"], g.get("gid"), g.get("state")) for g in games])
G.SLEEP = 0.3
out = []
for gid, meta in [("2021051118", {"date": "2026-10-05", "home": "라쿠텐 골든이글스", "away": "소프트뱅크 호크스", "venue": "라쿠텐 모바일 파크", "kind": "regular"})] + \
        [(g["gid"], {"date": "2026-10-05", "home": g["home"], "away": g["away"], "venue": g["venue"], "kind": "regular"}) for g in games if g.get("gid") and g["gid"] != "2021051118"][:2]:
    g = G.fetch_game(gid, meta)
    if g: out.append(g)
G.translate_plays(out)
os.makedirs("/tmp/pub", exist_ok=True)
for g in out:
    json.dump(g, open(f"/tmp/pub/{g['gid']}.json", "w"), ensure_ascii=False, indent=1)
print("saved", [g["gid"] for g in out])
