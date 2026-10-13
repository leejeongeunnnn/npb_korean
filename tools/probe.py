# 임시 점검 스크립트 (확인 후 삭제)
import re, json, requests
from bs4 import BeautifulSoup
H = {"User-Agent": "npb-korean-dashboard/1.0 (https://github.com/leejeongeunnnn/npb_korean)"}

def get(url, **kw):
    r = requests.get(url, headers=H, timeout=30, **kw); r.encoding = "utf-8"
    print(f"\n######## {url[:120]} -> {r.status_code}, {len(r.text)} bytes")
    return r

# 1) NPB 개인 페이지: 이름 읽기(가나) 위치
r = get("https://npb.jp/bis/players/31335139.html")
s = BeautifulSoup(r.text, "html.parser")
for m in re.finditer(r"[ぁ-ゖー・　 ]{4,}", s.get_text(" ")):
    print("KANA:", repr(m.group(0))); break
for tag in s.find_all(id=True)[:80]:
    t = tag.get_text(" ", strip=True)
    if t and len(t) < 60:
        print("ID:", tag.name, tag["id"], "=>", t)
print("TITLE:", s.title.get_text(strip=True) if s.title else None)

# 2) 명단 페이지 섹션 구조 (구단 코드 확인)
for code in ["g", "db", "e"]:
    r = get(f"https://npb.jp/bis/teams/rst_{code}.html")
    s = BeautifulSoup(r.text, "html.parser")
    heads = [th.get_text(" ", strip=True) for th in s.find_all("th")][:30]
    print("HEADS:", heads)
    caps = [t.get_text(" ", strip=True)[:40] for t in s.find_all(["h3", "h4", "caption"])][:15]
    print("CAPS:", caps)
    rows = s.find_all("tr")
    print("ROWS:", len(rows), "| sample:", [" | ".join(c.get_text(" ", strip=True) for c in rows[i].find_all(["td", "th"])) for i in range(0, min(len(rows), 6))])

# 3) 위키데이터 출생지
q = """
SELECT ?name ?item ?birth ?placeKo ?placeJa ?coord ?prefJa ?countryKo WHERE {
  VALUES ?name { "岩崎優"@ja "佐藤輝明"@ja "村上頌樹"@ja "近本光司"@ja }
  { ?item rdfs:label ?name } UNION { ?item skos:altLabel ?name }
  ?item wdt:P31 wd:Q5 .
  OPTIONAL { ?item wdt:P569 ?birth }
  OPTIONAL { ?item wdt:P19 ?place .
    OPTIONAL { ?place wdt:P625 ?coord }
    OPTIONAL { ?place rdfs:label ?placeKo FILTER(lang(?placeKo)="ko") }
    OPTIONAL { ?place rdfs:label ?placeJa FILTER(lang(?placeJa)="ja") }
    OPTIONAL { ?place wdt:P131* ?pref . ?pref wdt:P31 wd:Q50337 . ?pref rdfs:label ?prefJa FILTER(lang(?prefJa)="ja") }
    OPTIONAL { ?place wdt:P17 ?c . ?c rdfs:label ?countryKo FILTER(lang(?countryKo)="ko") }
  }
}"""
r = get("https://query.wikidata.org/sparql", params={"query": q, "format": "json"})
try:
    for b in r.json()["results"]["bindings"]:
        print("WD:", {k: v["value"][:60] for k, v in b.items()})
except Exception as e:
    print("WD ERR", e, r.text[:300])

# 4) 구장 지오코딩 (Nominatim / 국토지리원)
for qv in ["倉敷マスカットスタジアム", "沖縄セルラースタジアム那覇", "ほっともっとフィールド神戸"]:
    r = get("https://nominatim.openstreetmap.org/search", params={"q": qv, "format": "json", "limit": 1, "countrycodes": "jp"})
    print("NOMI:", r.text[:200])
    r = get("https://msearch.gsi.go.jp/address-search/AddressSearch", params={"q": qv})
    print("GSI:", r.text[:200])

# 5) 시즌 일정: 개막일 부근 날짜 응답
r = get("https://baseball.yahoo.co.jp/npb/schedule/", params={"date": "2026-03-27"})
s = BeautifulSoup(r.text, "html.parser")
items = s.find_all("li", class_="bb-score__item")
print("OPENING games:", len(items), [i.get_text(" ", strip=True)[:80] for i in items[:2]])
desc = [d.get_text(strip=True) for d in s.find_all("p", class_="bb-score__description")]
print("VENUES raw:", desc[:8])
