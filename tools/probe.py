import re, requests
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
GID = "2021051118"
def get(path):
    r = requests.get(f"https://baseball.yahoo.co.jp/npb/game/{GID}/{path}", headers=H, timeout=20); r.encoding = "utf-8"
    print(f"\n######## {path} -> {r.status_code} len={len(r.text)} final={r.url}")
    return BeautifulSoup(r.text, "html.parser")
s = get("index")
nav = [(a.get_text(strip=True), a["href"]) for a in s.select("a[href*='/npb/game/%s/']" % GID)]
print("TABS", sorted(set(nav))[:20])
for t in s.find_all("table")[:8]:
    rows = [[c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])] for r in t.find_all("tr")[:6]]
    print("TABLE", t.get("class"), t.get("id"), rows)
for kw in ["責任投手", "勝利投手", "敗戦投手", "セーブ", "本塁打", "得点経過", "スコア"]:
    el = s.find(string=re.compile(kw))
    if el:
        par = el.find_parent(["section", "div", "table"])
        print("KW", kw, "->", par.get("class") if par else None, str(par)[:900].replace("\n", " ") if par else "")
s = get("stats")
for t in s.find_all("table"):
    cls = t.get("class")
    rows = t.find_all("tr")
    print("STATS TABLE", cls, "rows", len(rows))
    for r in rows[:4] + rows[-2:]:
        print("   ", [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])][:16], [ (c.get("class")) for c in r.find_all("td")[:2]])
for path in ["score", "text"]:
    s = get(path)
    for kw in ["得点", "タイムリー", "ホームラン", "犠牲フライ"]:
        els = s.find_all(string=re.compile(kw))[:2]
        for el in els:
            par = el.find_parent(["li", "tr", "div", "section"])
            print("  ", path, kw, "->", par.get("class") if par else None, (par.get_text(" ", strip=True) if par else "")[:300])
    secs = [ (x.name, x.get("class")) for x in s.find_all(["section"], limit=12)]
    print("  SECTIONS", secs)
