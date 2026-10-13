import re, requests
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
def get(url):
    r = requests.get(url, headers=H, timeout=20); r.encoding = r.apparent_encoding if "npb.jp" in url else "utf-8"
    print(f"\n######## {url} -> {r.status_code} enc={r.encoding}")
    return BeautifulSoup(r.text, "html.parser")

s = get("https://npb.jp/bis/teams/rst_t.html")
for t in s.find_all("table"):
    rows = t.find_all("tr")
    if len(rows) > 10:
        print("ROSTER TABLE class=", t.get("class"), "rows=", len(rows))
        for r in rows[:6]:
            print("  ROW", [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])], r.find("a")["href"] if r.find("a") else "")
        break
for pid in ["31335139", "51355139"]:
    p = get(f"https://npb.jp/bis/players/{pid}.html")
    for t in p.find_all("table", limit=4):
        rows = [[c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])] for r in t.find_all("tr")[:14]]
        print("TABLE id=", t.get("id"), "class=", t.get("class"), rows)
    h = p.find(id=re.compile("pc_v_name|pc_bio", re.I))
    print("BIO", str(p.find(id="pc_bio"))[:1500] if p.find(id="pc_bio") else "no pc_bio")
    print("NAME", p.find(id="pc_v_name").get_text("|", strip=True) if p.find(id="pc_v_name") else "")
    txt = p.get_text("|", strip=True)
    for kw in ["生年月日", "出身", "身長", "経歴", "投打", "ドラフト", "ポジション", "背番号"]:
        i = txt.find(kw); print(kw, "=>", txt[max(0, i-10): i+100] if i >= 0 else "NOT FOUND")
# Yahoo 선수 페이지 출신지 확인 (팀 페이지에서 링크 찾기)
s = get("https://baseball.yahoo.co.jp/npb/teams/5/memberlist?kind=p")
s = get("https://baseball.yahoo.co.jp/npb/teams/5/index")
links = sorted({a["href"] for a in s.find_all("a", href=True) if "/npb/player/" in a["href"]})
print("yahoo player links", len(links), links[:5])
ml = sorted({a["href"] for a in s.find_all("a", href=True) if "member" in a["href"] or "player" in a["href"]})
print("member-ish links", ml[:15])
if links:
    u = links[0] if links[0].startswith("http") else "https://baseball.yahoo.co.jp" + links[0]
    p = get(u); txt = p.get_text("|", strip=True)
    for kw in ["生年月日", "出身地", "身長", "経歴", "投打", "ドラフト"]:
        i = txt.find(kw); print("Y", kw, "=>", txt[max(0, i-10): i+100] if i >= 0 else "NOT FOUND")
    for el in p.find_all(class_=re.compile("profile", re.I), limit=4):
        print("YPROF", el.name, el.get("class"), str(el)[:1200].replace("\n", " "))
