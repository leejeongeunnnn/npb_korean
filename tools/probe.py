# 임시 점검 스크립트: 선수 명단/개인 페이지 HTML 구조 확인용 (확인 후 삭제)
import re, requests
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
def soup(url):
    r = requests.get(url, headers=H, timeout=20); r.encoding = "utf-8"
    print(f"\n######## {url} -> {r.status_code}, {len(r.text)} bytes")
    return BeautifulSoup(r.text, "html.parser")
def kv(s, limit=40):
    n = 0
    for tr in s.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if cells:
            print("  ROW:", " | ".join(cells)[:200]); n += 1
            if n >= limit: break
    for dl in s.find_all("dl")[:15]:
        print("  DL:", dl.get_text(" | ", strip=True)[:200])

s = soup("https://npb.jp/bis/teams/rst_t.html")
links = [(a.get_text(strip=True), a["href"]) for a in s.select("table a[href]")]
print("NPB links sample:", links[:6])
first = next((h for t, h in links if "players" in h), None)
if first:
    url = requests.compat.urljoin("https://npb.jp/bis/teams/rst_t.html", first)
    p = soup(url); kv(p)
    print("TEXT:", re.sub(r"\s+", " ", p.get_text(" "))[:1500])

y = soup("https://baseball.yahoo.co.jp/npb/teams/5/memberlist?kind=p")
ylinks = [(a.get_text(strip=True), a["href"]) for a in y.find_all("a", href=True) if "/player/" in a["href"]]
print("YAHOO player links:", ylinks[:6], "count", len(ylinks))
kinds = sorted({a["href"] for a in y.find_all("a", href=True) if "memberlist" in a["href"]})
print("YAHOO memberlist tabs:", kinds)
if ylinks:
    url = requests.compat.urljoin("https://baseball.yahoo.co.jp/", ylinks[0][1])
    p = soup(url); kv(p)
    print("TEXT:", re.sub(r"\s+", " ", p.get_text(" "))[:1800])
