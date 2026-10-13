# 임시 조사 스크립트: 데이터 소스 HTML 구조 확인용 (조사 후 삭제)
import re, requests
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

def get(url, **kw):
    r = requests.get(url, headers=H, timeout=20, **kw); r.encoding = "utf-8"
    print(f"\n######## {url} -> {r.status_code} len={len(r.text)}")
    return BeautifulSoup(r.text, "html.parser")

# 1) Yahoo 선수 명단: 링크 패턴
s = get("https://baseball.yahoo.co.jp/npb/teams/5/memberlist", params={"kind": "p"})
links = [a["href"] for a in s.find_all("a", href=True) if "/npb/player/" in a["href"]]
print("player links:", len(links), links[:5])
for k in ["c", "i", "o"]:
    s2 = get("https://baseball.yahoo.co.jp/npb/teams/5/memberlist", params={"kind": k})
    l2 = [a["href"] for a in s2.find_all("a", href=True) if "/npb/player/" in a["href"]]
    print("kind", k, len(l2), l2[:2])

# 2) Yahoo 선수 상세
if links:
    u = links[0] if links[0].startswith("http") else "https://baseball.yahoo.co.jp" + links[0]
    p = get(u)
    main = p.find(id=re.compile("player|prof", re.I)) or p
    txt = p.get_text("|", strip=True)
    for kw in ["生年月日", "出身地", "身長", "体重", "投打", "経歴", "ドラフト", "ポジション", "背番号"]:
        i = txt.find(kw); print(kw, "=>", txt[max(0, i-20): i+120] if i >= 0 else "NOT FOUND")
    for tag in p.find_all(["table", "dl"], limit=6):
        print("TAG", tag.name, tag.get("class"), str(tag)[:700].replace("\n", " "))
    for el in p.find_all(class_=re.compile("bb-profile|ProfileList|profile", re.I), limit=6):
        print("PROFILECLS", el.name, el.get("class"), str(el)[:900].replace("\n", " "))

# 3) Yahoo 구단 월별 일정
s = get("https://baseball.yahoo.co.jp/npb/teams/5/schedule", params={"month": "2026-07"})
tbls = s.find_all("table")
print("tables:", len(tbls), [t.get("class") for t in tbls[:4]])
for t in tbls[:2]:
    print(str(t)[:1800].replace("\n", " "))
cal = s.find_all(class_=re.compile("bb-calendar|schedule", re.I), limit=4)
for c in cal:
    print("CAL", c.name, c.get("class"), str(c)[:1500].replace("\n", " "))

# 4) npb.jp 명단 / 선수 페이지 (비교용)
s = get("https://npb.jp/bis/teams/rst_t.html")
t = s.find("table"); print("npb roster table:", str(t)[:1500].replace("\n", " ") if t else None)
pl = [a["href"] for a in s.find_all("a", href=True) if "/bis/players/" in a["href"]]
print("npb player links", len(pl), pl[:3])
if pl:
    p = get("https://npb.jp" + pl[0] if pl[0].startswith("/") else pl[0])
    for tag in p.find_all("table", limit=3):
        print("NPBTAG", tag.get("id"), tag.get("class"), str(tag)[:1200].replace("\n", " "))
