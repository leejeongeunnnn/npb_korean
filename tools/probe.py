import re, requests
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
def get(url):
    r = requests.get(url, headers=H, timeout=20); r.encoding = "utf-8"
    print(f"\n######## {url} -> {r.status_code} len={len(r.text)}")
    return BeautifulSoup(r.text, "html.parser")
s = get("https://baseball.yahoo.co.jp/npb/teams/5/players")
links = []
for a in s.find_all("a", href=True):
    if re.search(r"/npb/player/\d+/top", a["href"]) and a["href"] not in links: links.append(a["href"])
print("players links", len(links), links[:4])
tb = s.find_all("table")
print("tables", len(tb), [t.get("class") for t in tb])
for t in tb[:1]:
    for r in t.find_all("tr")[:4]:
        print(" ROW", [c.get_text(" ", strip=True) for c in r.find_all(["td","th"])], [a.get("href") for a in r.find_all("a")])
for u in links[:1] + links[30:31]:
    p = get("https://baseball.yahoo.co.jp" + u)
    nm = p.find(class_=re.compile("bb-profile__name")); print("NAME", nm.get_text("|", strip=True) if nm else None)
    for el in p.find_all(class_=re.compile("bb-profile__(title|number|position|name|kana)"), limit=8):
        print(" P", el.get("class"), el.get_text("|", strip=True))
    for el in p.find_all(["dl", "table"], class_=re.compile("profile|Profile", re.I), limit=3):
        print(" DL", el.get("class"), str(el)[:1400].replace("\n", " "))
    lst = p.find(class_=re.compile("bb-profile__list|ProfileList"))
    print(" LIST", str(lst)[:2000].replace("\n", " ") if lst else "none")
