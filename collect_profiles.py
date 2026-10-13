# -*- coding: utf-8 -*-
"""
선수 프로필 · 출신지 · 원정 이동거리 수집 (주 1회 실행, profiles.yml)

생성 파일
  data/roster/<구단코드>.json   구단별 선수단 + 개인 프로필 (마이팀 탭)
  data/hometowns.json           12구단 전체 선수 출신지 좌표 (출신지 지도)
  data/travel.json              구단별 시즌 원정 이동거리·경로 (이동거리 분석)
  data/venues.json              경기가 열린 모든 구장 좌표
  data/cache/*.json             재실행 시 다시 받지 않도록 저장하는 캐시

출처
  선수단·프로필: NPB 공식(npb.jp) 구단 선수 일람 / 개인 성적 페이지
  출신지(출생지)·좌표: 위키데이터(Wikidata) — NPB 생년월일과 일치하는 인물만 채택
  시즌 경기·구장: Yahoo! Japan 스포츠 일정
  구장 좌표: 12개 홈구장은 teams.json, 그 외 지방구장은 OpenStreetMap Nominatim → 국토지리원 주소검색
"""

import os
import re
import json
import math
import time
import datetime

import requests
from bs4 import BeautifulSoup

import collect as C
from kana_ko import kana_to_hangul

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
CACHE = os.path.join(DATA, "cache")
ROSTER_DIR = os.path.join(DATA, "roster")
SEASON = C.SEASON
SEASON_START = os.environ.get("NPB_SEASON_START", f"{SEASON}-03-27")
UA = {"User-Agent": "npb-korean-dashboard/1.0 (+https://github.com/leejeongeunnnn/npb_korean)"}

S = requests.Session()
S.headers.update(C.HEADERS)


def jload(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def jsave(path, obj, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    print(f"[OK] {os.path.relpath(path, BASE)} ({os.path.getsize(path):,} bytes)")


def get(url, tries=3, **kw):
    for i in range(tries):
        try:
            r = S.get(url, timeout=25, **kw)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r
            print(f"[WARN] {url} -> {r.status_code}")
        except Exception as e:
            print(f"[WARN] {url} -> {e}")
        time.sleep(2 * (i + 1))
    return None


def haversine(a, b):
    """두 좌표(lat, lon) 사이 대권거리(km)."""
    R = 6371.0088
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


TEAMS = jload(os.path.join(DATA, "teams.json"), {})
ALL_TEAMS = TEAMS.get("central", []) + TEAMS.get("pacific", [])
TEAM_BY_KR = {t["name"]: t for t in ALL_TEAMS}

# 도도부현 일본어 → 한국어 (경계 데이터와 동일한 표기)
PREF_KO = {f["properties"]["ja"]: f["properties"]["ko"]
           for f in jload(os.path.join(DATA, "geo", "japan_prefs.geojson"), {"features": []})["features"]}

TRANS_CACHE_PATH = os.path.join(CACHE, "translate.json")
TRANS = jload(TRANS_CACHE_PATH, {})


def tr(text):
    """번역 + 영구 캐시 (학교명·지명은 매주 다시 번역하지 않음)."""
    if not text:
        return ""
    if text in TRANS:
        return TRANS[text]
    out = C.translate_text_kr(text)
    TRANS[text] = out
    return out


# ----------------------------------------------------------------------------
# 1) 선수단 명단 (구단별 1페이지)
# ----------------------------------------------------------------------------
POS_KO = {"監督": "감독", "投手": "투수", "捕手": "포수", "内野手": "내야수", "外野手": "외야수"}
LEFT_TEAM = re.compile(r"自由契約|退団|移籍|トレード|引退|ウェイバー|任意引退|保留")


def parse_roster(code):
    url = f"https://npb.jp/bis/teams/rst_{code}.html"
    r = get(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    kind, pos = "지배하", None
    out = []
    for el in soup.find_all(["h3", "h4", "caption", "tr"]):
        if el.name != "tr":
            t = el.get_text(strip=True)
            if "育成" in t:
                kind = "육성"
            elif "支配下" in t:
                kind = "지배하"
            continue
        cells = el.find_all(["th", "td"], recursive=False)
        texts = [c.get_text(" ", strip=True) for c in cells]
        if len(texts) >= 2 and texts[1] in POS_KO and texts[0].startswith("No"):
            pos = texts[1]
            continue
        if pos is None or len(texts) < 3:
            continue
        a = cells[1].find("a", href=True) if len(cells) > 1 else None
        note = texts[-1] if len(texts) >= 5 else ""
        if pos != "監督" and LEFT_TEAM.search(note):
            continue
        out.append({
            "no": texts[0],
            "name_jp": re.sub(r"[\s　]+", " ", texts[1]).strip(),
            "birth": texts[2].replace(".", "-") if re.match(r"\d{4}\.\d{2}\.\d{2}", texts[2]) else "",
            "height": texts[3] if pos != "監督" and len(texts) > 3 else "",
            "weight": texts[4] if pos != "監督" and len(texts) > 4 else "",
            "pos_jp": pos,
            "kind": kind,
            "note": note,
            "url": requests.compat.urljoin(url, a["href"]) if a else "",
        })
    return out


# ----------------------------------------------------------------------------
# 2) 개인 페이지 (프로필 + 올 시즌 성적)
# ----------------------------------------------------------------------------
def _row_cells(tr):
    return [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"], recursive=False)]


def _ip(text):
    """'74 .1' / '74.1' / '46 46 .1'(중첩 칸) / '74' → 이닝(소수 = 1/3 단위)"""
    t = (text or "").replace("\u3000", " ")
    m = re.search(r"(\d+)\s*\.(\d)", t)
    if m:
        return int(m.group(1)) + int(m.group(2)) / 3.0
    m = re.search(r"\d+", t)
    return float(m.group(0)) if m else 0.0


def parse_player(url):
    r = get(url)
    if not r:
        return {}
    soup = BeautifulSoup(r.text, "html.parser")
    info = {}
    kana = soup.find(id="pc_v_kana")
    info["kana"] = kana.get_text(strip=True) if kana else ""
    for tr_ in soup.find_all("tr"):
        c = _row_cells(tr_)
        if len(c) == 2 and c[0] in ("ポジション", "投打", "身長／体重", "生年月日", "経歴", "ドラフト"):
            info[c[0]] = c[1]

    # 올 시즌 성적 (투수/타자 표 각각에서 해당 연도 행)
    season = {}
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        head = _row_cells(rows[0])
        if "年度" not in head:
            continue
        kind = "pit" if "防御率" in head else ("bat" if "打率" in head else None)
        if not kind:
            continue
        for tr_ in rows[1:]:
            c = _row_cells(tr_)
            if c and c[0] == str(SEASON) and len(c) >= len(head) - 1:
                row = dict(zip(head, c))
                season[kind] = row
                break
    stats = {}
    if "pit" in season:
        p = season["pit"]
        stats["pit"] = {"g": p.get("登板", ""), "w": p.get("勝利", ""), "l": p.get("敗北", ""),
                        "sv": p.get("セーブ", ""), "hld": p.get("H", p.get("ホールド", "")),
                        "ip": round(_ip(p.get("投球回", "0")), 1), "so": p.get("三振", ""),
                        "era": p.get("防御率", "")}
    if "bat" in season:
        b = season["bat"]
        stats["bat"] = {"g": b.get("試合", ""), "ab": b.get("打数", ""), "h": b.get("安打", ""),
                        "hr": b.get("本塁打", ""), "rbi": b.get("打点", ""), "sb": b.get("盗塁", ""),
                        "avg": b.get("打率", ""), "obp": b.get("出塁率", ""), "slg": b.get("長打率", "")}
    info["stats"] = stats
    return info


def draft_ko(text):
    t = (text or "").strip()
    if not t:
        return ""
    t2 = re.sub(r"(\d{4})年", r"\1년 ", t)
    t2 = re.sub(r"育成ドラフト\s*(\d+)位", r"육성 드래프트 \1순위", t2)
    t2 = re.sub(r"育成選手ドラフト\s*(\d+)位", r"육성 드래프트 \1순위", t2)
    t2 = re.sub(r"ドラフト\s*(\d+)位", r"드래프트 \1순위", t2)
    t2 = (t2.replace("自由獲得枠", "자유획득 범위(역지명)").replace("希望入団枠", "희망 입단 범위")
             .replace("逆指名", "역지명").replace("外国人選手", "외국인 선수"))
    if C.JP_RE.search(t2):
        t2 = tr(t2)
    return re.sub(r"\s{2,}", " ", t2).strip()


def throws_ko(text):
    return (text or "").replace("右", "우").replace("左", "좌").replace("両", "양").replace("投", "투").replace("打", "타")


def schools_ko(text):
    if not text:
        return []
    out = []
    for part in [p.strip() for p in re.split(r"\s*[-－–]\s*", text) if p.strip()]:
        q = part
        if re.search(r"[一-鿿]高$", q):
            q = q + "等学校"
        elif re.search(r"[一-鿿]大$", q):
            q = q + "学"
        out.append({"jp": part, "ko": tr(q)})
    return out


def name_ko(name_jp, kana):
    k = C.translate_player_name(name_jp)
    if k != name_jp:
        return k
    if kana:
        return kana_to_hangul(kana)
    return tr(name_jp)


def age_on(birth, today):
    try:
        y, m, d = map(int, birth.split("-"))
        return today.year - y - ((today.month, today.day) < (m, d))
    except Exception:
        return None


# ----------------------------------------------------------------------------
# 3) 위키데이터 출생지 (생년월일이 일치하는 야구 선수만 채택)
# ----------------------------------------------------------------------------
WD_CACHE_PATH = os.path.join(CACHE, "wikidata_birthplace.json")
WD = jload(WD_CACHE_PATH, {})

WD_QUERY = """
SELECT ?name ?item ?birth ?placeKo ?placeJa ?coord ?prefJa ?countryKo WHERE {
  VALUES ?name { %s }
  { ?item rdfs:label ?name } UNION { ?item skos:altLabel ?name }
  ?item wdt:P31 wd:Q5 .
  OPTIONAL { ?item wdt:P569 ?birth }
  OPTIONAL { ?item wdt:P19 ?place .
    OPTIONAL { ?place wdt:P625 ?coord }
    OPTIONAL { ?place rdfs:label ?placeKo FILTER(lang(?placeKo)="ko") }
    OPTIONAL { ?place rdfs:label ?placeJa FILTER(lang(?placeJa)="ja") }
    OPTIONAL { ?place wdt:P131* ?pref . ?pref wdt:P31 wd:Q50337 .
               ?pref rdfs:label ?prefJa FILTER(lang(?prefJa)="ja") }
    OPTIONAL { ?place wdt:P17 ?c . ?c rdfs:label ?countryKo FILTER(lang(?countryKo)="ko") }
  }
}"""


def wd_key(name_jp, birth):
    clean = re.sub("[ \u3000]", "", name_jp)
    return clean + "|" + birth


def name_variants(name_jp):
    n = re.sub(r"[\s　]", "", name_jp)
    vs = {n, n.replace("髙", "高").replace("﨑", "崎").replace("德", "徳").replace("濵", "濱")}
    return vs


def fetch_birthplaces(players):
    """players: [(name_jp, birth)] — 캐시에 없는 것만 조회."""
    todo = [(n, b) for n, b in players if b and wd_key(n, b) not in WD]
    print(f"[WD] 조회 대상 {len(todo)}명 (캐시 {len(WD)}건)")
    for i in range(0, len(todo), 40):
        batch = todo[i:i + 40]
        names = set()
        for n, _ in batch:
            names |= name_variants(n)
        values = " ".join(f'"{x}"@ja' for x in names)
        try:
            r = requests.get("https://query.wikidata.org/sparql",
                             params={"query": WD_QUERY % values, "format": "json"},
                             headers=UA, timeout=60)
            rows = r.json()["results"]["bindings"] if r.status_code == 200 else []
        except Exception as e:
            print(f"[WARN] wikidata: {e}")
            rows = []
        by = {}
        for b in rows:
            v = {k: x["value"] for k, x in b.items()}
            by.setdefault(v["name"], []).append(v)
        for n, birth in batch:
            cands = []
            for var in name_variants(n):
                cands += by.get(var, [])
            hit = next((c for c in cands if c.get("birth", "")[:10] == birth and c.get("coord")), None)
            if hit:
                lon, lat = map(float, re.findall(r"[-\d.]+", hit["coord"])[:2])
                pref_ja = hit.get("prefJa", "")
                WD[wd_key(n, birth)] = {
                    "lat": round(lat, 4), "lon": round(lon, 4),
                    "place_ja": hit.get("placeJa", ""), "place_ko": hit.get("placeKo", ""),
                    "pref_ja": pref_ja, "country": hit.get("countryKo", ""),
                    "wd": hit["item"].rsplit("/", 1)[-1],
                }
        time.sleep(1.5)
    jsave(WD_CACHE_PATH, WD)


def birthplace_of(name_jp, birth):
    w = WD.get(wd_key(name_jp, birth))
    if not w:
        return None
    pref_ko = PREF_KO.get(w["pref_ja"], "")
    place_ko = w["place_ko"] or (tr(w["place_ja"]) if w["place_ja"] else "")
    foreign = bool(w["country"]) and w["country"] != "일본"
    return {"lat": w["lat"], "lon": w["lon"], "pref": pref_ko, "place": place_ko,
            "country": w["country"] or ("일본" if pref_ko else ""), "foreign": foreign, "wd": w["wd"]}


# ----------------------------------------------------------------------------
# 4) 시즌 전체 경기 기록 (지난 날짜는 캐시) + 구장 좌표
# ----------------------------------------------------------------------------
SEASON_CACHE_PATH = os.path.join(CACHE, "season_games.json")

HOME_VENUE_JP = {   # Yahoo 구장 약칭 → 홈 구단
    "東京ドーム": "요미우리 자이언츠", "甲子園": "한신 타이거스", "バンテリンドーム": "주니치 드래곤즈",
    "横浜": "요코하마 DeNA 베이스타스", "神宮": "야쿠르트 스왈로스", "マツダスタジアム": "히로시마 도요 카프",
    "みずほPayPay": "소프트뱅크 호크스", "京セラD大阪": "오릭스 버팔로즈", "ZOZOマリン": "지바 롯데 마린스",
    "楽天モバイル": "라쿠텐 골든이글스", "ベルーナドーム": "세이부 라이온즈", "エスコンF": "니혼햄 파이터즈",
}
# 지방구장 약칭 → 검색용 정식 명칭
VENUE_FULLNAME = {
    "ほっと神戸": "ほっともっとフィールド神戸", "那覇": "沖縄セルラースタジアム那覇", "倉敷": "倉敷マスカットスタジアム",
    "富山": "富山市民球場アルペンスタジアム", "岐阜": "岐阜県営長良川球場", "函館": "函館オーシャンスタジアム",
    "旭川": "旭川スタルヒン球場", "釧路": "釧路市民球場", "帯広": "帯広の森野球場", "松山": "坊っちゃんスタジアム",
    "北九州": "北九州市民球場", "鹿児島": "鹿児島県立鴨池野球場", "熊本": "藤崎台県営野球場", "長崎": "長崎県営野球場",
    "宇都宮": "宇都宮清原球場", "福島": "福島県営あづま球場", "いわき": "ヨークいわきスタジアム",
    "郡山": "ヨーク開成山スタジアム", "前橋": "上毛新聞敷島球場", "静岡": "静岡草薙球場", "浜松": "浜松球場",
    "金沢": "石川県立野球場", "新潟": "HARD OFF ECOスタジアム新潟", "秋田": "こまちスタジアム",
    "盛岡": "きたぎんボールパーク", "山形": "山形県野球場", "県営大宮": "埼玉県営大宮球場", "大宮": "埼玉県営大宮球場",
    "弘前": "はるか夢球場", "八戸": "八戸市長根公園野球場", "豊橋": "豊橋市民球場", "米子": "米子市民球場",
    "松江": "松江市営野球場", "高知": "高知県立春野運動公園野球場", "宮崎": "ひなたサンマリンスタジアム宮崎",
    "佐世保": "佐世保市総合グラウンド野球場", "上田": "上田県営球場", "長野": "長野オリンピックスタジアム",
    "松本": "松本市野球場", "東京D": "東京ドーム", "甲府": "山日YBS球場", "和歌山": "紀三井寺公園野球場",
    "姫路": "ウインク球場", "福山": "ぶんちゃんしまなみ球場", "呉": "呉市二河野球場", "三次": "三次きんさいスタジアム",
}

VENUE_CACHE_PATH = os.path.join(CACHE, "venues_geo.json")
VENUE_GEO = jload(VENUE_CACHE_PATH, {})


def geocode_venue(short):
    if short in VENUE_GEO:
        return VENUE_GEO[short]
    if short in HOME_VENUE_JP:
        t = TEAM_BY_KR[HOME_VENUE_JP[short]]
        VENUE_GEO[short] = {"lat": t["lat"], "lon": t["lon"], "name_ko": t["stadium"], "src": "teams.json"}
        return VENUE_GEO[short]
    full = VENUE_FULLNAME.get(short, short)
    res = None
    for q in (full, f"{short} 野球場"):
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search",
                             params={"q": q, "format": "json", "limit": 1, "countrycodes": "jp"},
                             headers=UA, timeout=20)
            js = r.json() if r.status_code == 200 else []
        except Exception:
            js = []
        time.sleep(1.1)   # Nominatim 이용 정책: 초당 1회
        if js:
            res = {"lat": round(float(js[0]["lat"]), 5), "lon": round(float(js[0]["lon"]), 5), "src": "OSM Nominatim"}
            break
    if not res:
        try:
            r = requests.get("https://msearch.gsi.go.jp/address-search/AddressSearch", params={"q": full}, timeout=20)
            js = r.json() if r.status_code == 200 else []
            if js:
                lon, lat = js[0]["geometry"]["coordinates"]
                res = {"lat": round(lat, 5), "lon": round(lon, 5), "src": "국토지리원(시정촌 대표점)"}
        except Exception:
            pass
    if res:
        res["name_ko"] = C.venue_kr(short)
        res["name_jp"] = full
        VENUE_GEO[short] = res
    else:
        print(f"[WARN] 구장 좌표 못 찾음: {short}")
    return res


def update_season_games():
    cache = jload(SEASON_CACHE_PATH, {})
    today = C.now_jst().date()
    d = datetime.date.fromisoformat(SEASON_START)
    fetched = 0
    while d < today:
        ds = d.isoformat()
        if ds not in cache:
            games = C.fetch_games_by_date(ds)
            cache[ds] = [{k: g.get(k, "") for k in ("home", "away", "score_home", "score_away", "state", "venue_jp", "series")}
                         for g in games]
            fetched += 1
            time.sleep(0.4)
        d += datetime.timedelta(days=1)
    print(f"[SEASON] 새로 받은 날짜 {fetched}일, 누적 {len(cache)}일")
    jsave(SEASON_CACHE_PATH, cache, compact=True)
    return cache


def compute_travel(season):
    """구단별 이동거리: 경기 순서대로 구장 사이를 직접 이동한다고 가정 (시즌 시작은 홈구장)."""
    out = {}
    for t in ALL_TEAMS:
        name, home = t["name"], (t["lat"], t["lon"])
        pos, pos_name = home, t["stadium"]
        total, legs, hg, ag = 0.0, [], 0, 0
        path = [[t["lat"], t["lon"]]]
        for ds in sorted(season):
            for g in season[ds]:
                if name not in (g["home"], g["away"]) or g.get("state") not in ("final", "cancel"):
                    continue
                geo = geocode_venue(g["venue_jp"]) if g.get("venue_jp") else None
                if geo:
                    loc, loc_name = (geo["lat"], geo["lon"]), geo.get("name_ko", g["venue_jp"])
                else:   # 좌표를 못 찾으면 홈 팀 홈구장으로 근사
                    ht = TEAM_BY_KR.get(g["home"])
                    loc, loc_name = ((ht["lat"], ht["lon"]), ht["stadium"]) if ht else (pos, pos_name)
                if g["home"] == name:
                    hg += 1
                else:
                    ag += 1
                km = haversine(pos, loc)
                if km > 1.0:
                    total += km
                    legs.append({"date": ds, "from": pos_name, "to": loc_name, "km": round(km)})
                    path.append([round(loc[0], 4), round(loc[1], 4)])
                pos, pos_name = loc, loc_name
        longest = max(legs, key=lambda x: x["km"]) if legs else None
        out[name] = {"total_km": round(total), "moves": len(legs), "home_games": hg, "away_games": ag,
                     "longest": longest, "path": path, "legs": legs}
    return out


# ----------------------------------------------------------------------------
# 실행
# ----------------------------------------------------------------------------
def main():
    today = C.now_jst().date()
    print(f"=== 프로필·공간 데이터 수집 ({today}, 시즌 {SEASON}) ===")

    rosters = {}
    for t in ALL_TEAMS:
        lst = parse_roster(t["code"])
        print(f"[ROSTER] {t['name']} ({t['code']}): {len(lst) if lst else 0}명")
        rosters[t["code"]] = lst or []
        time.sleep(0.5)

    # 개인 페이지
    for code, lst in rosters.items():
        for p in lst:
            if p["pos_jp"] == "監督" or not p["url"]:
                p["detail"] = {}
                continue
            p["detail"] = parse_player(p["url"])
            time.sleep(0.35)
        print(f"[DETAIL] {code}: 완료")

    # 위키데이터 출생지
    fetch_birthplaces([(p["name_jp"], p["birth"]) for lst in rosters.values() for p in lst])

    hometowns = []
    for t in ALL_TEAMS:
        lst = rosters[t["code"]]
        players, manager = [], None
        for p in lst:
            d = p.get("detail", {})
            bp = birthplace_of(p["name_jp"], p["birth"])
            hw = d.get("身長／体重", "")
            m = re.match(r"(\d+)cm／(\d+)kg", hw)
            entry = {
                "no": p["no"], "name": name_ko(p["name_jp"], d.get("kana", "")), "name_jp": p["name_jp"],
                "kana": d.get("kana", ""), "pos": POS_KO.get(p["pos_jp"], p["pos_jp"]), "kind": p["kind"],
                "birth": p["birth"], "age": age_on(p["birth"], today),
                "height": int(m.group(1)) if m else (int(p["height"]) if p["height"].isdigit() else None),
                "weight": int(m.group(2)) if m else (int(p["weight"]) if p["weight"].isdigit() else None),
                "throws": throws_ko(d.get("投打", "")), "schools": schools_ko(d.get("経歴", "")),
                "draft": draft_ko(d.get("ドラフト", "")), "stats": d.get("stats", {}),
                "birthplace": bp, "url": p["url"],
            }
            if p["pos_jp"] == "監督":
                manager = {k: entry[k] for k in ("name", "name_jp", "birth", "age", "birthplace")}
                continue
            players.append(entry)
            if bp:
                hometowns.append({"t": t["name"], "n": entry["name"], "pos": entry["pos"], "kind": p["kind"],
                                  "lat": bp["lat"], "lon": bp["lon"], "pref": bp["pref"], "place": bp["place"],
                                  "country": bp["country"], "foreign": bp["foreign"]})
        found = sum(1 for x in players if x["birthplace"])
        jsave(os.path.join(ROSTER_DIR, f"{t['code']}.json"), {
            "team": t["name"], "code": t["code"], "updated": today.isoformat(), "season": SEASON,
            "manager": manager, "players": players,
            "coverage": {"players": len(players), "birthplace": found},
        })
    total_players = sum(len(v) for v in rosters.values())
    jsave(os.path.join(DATA, "hometowns.json"), {
        "updated": today.isoformat(), "total_players": total_players, "points": hometowns,
        "source": "출생지: 위키데이터(생년월일 일치 확인) · 선수단: NPB.jp",
    }, compact=True)

    season = update_season_games()
    travel = compute_travel(season)
    jsave(os.path.join(DATA, "travel.json"), {
        "updated": today.isoformat(), "season_start": SEASON_START,
        "method": "경기 순서대로 구장 사이를 대권거리(직선)로 이동한다고 가정. 시즌 시작 위치는 홈구장. "
                  "실제 이동(귀가·숙소 경유·교통수단 경로)은 반영하지 않음.",
        "teams": travel,
    }, compact=True)
    jsave(os.path.join(DATA, "venues.json"), {
        "updated": today.isoformat(),
        "venues": [{"short": k, **v} for k, v in sorted(VENUE_GEO.items())],
    })
    jsave(VENUE_CACHE_PATH, VENUE_GEO)
    jsave(TRANS_CACHE_PATH, TRANS)
    print(f"=== 완료: 선수 {total_players}명, 출생지 확인 {len(hometowns)}명 ===")


if __name__ == "__main__":
    main()
