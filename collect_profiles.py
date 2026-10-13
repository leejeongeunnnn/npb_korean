# -*- coding: utf-8 -*-
"""
마이팀 공간분석용 데이터 수집 (하루 1회, daily.yml).

  python collect_profiles.py                 # 시즌 일정 + (7일 지났으면) 선수 프로필
  python collect_profiles.py --profiles      # 선수 프로필 강제 갱신
  python collect_profiles.py --season-only   # 시즌 일정만

출력:
  data/season.json             12개 구단 시즌 전 경기 (날짜·상대·홈/원정·구장 좌표·결과)
  data/profiles/<코드>.json    구단별 선수 프로필 (한국어)
  data/profiles/index.json     갱신 시각
  data/cache/translate.json    번역 캐시 (같은 학교명 등 재번역 방지)
  data/geo/venue_cache.json    지방 구장 좌표 캐시 (OpenStreetMap Nominatim)
"""
import os, re, sys, json, time, datetime

import requests
from bs4 import BeautifulSoup

import collect as C   # 번역·팀명 등 공용 함수 재사용

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
GEO = os.path.join(DATA, "geo")
PROF_DIR = os.path.join(DATA, "profiles")
CACHE_DIR = os.path.join(DATA, "cache")
SLEEP = 0.35          # 요청 간 대기(초) - 상대 서버 부담 줄이기
PROFILE_MAX_AGE_DAYS = 6
TIME_BUDGET_MIN = float(os.environ.get("TIME_BUDGET_MIN", "70"))   # 이 시간을 넘기면 저장하고 종료 (다음 실행에서 이어서)
START = time.time()


def time_left():
    return TIME_BUDGET_MIN * 60 - (time.time() - START)

# 구단: 한국어명 → (Yahoo 팀 ID, npb.jp 코드, 파일 코드, 일본어 약칭)
TEAMS = {
    "요미우리 자이언츠":        ("1",   "g",  "giants",   "巨人"),
    "야쿠르트 스왈로스":        ("2",   "s",  "swallows", "ヤクルト"),
    "요코하마 DeNA 베이스타스": ("3",   "db", "baystars", "DeNA"),
    "주니치 드래곤즈":          ("4",   "d",  "dragons",  "中日"),
    "한신 타이거스":            ("5",   "t",  "tigers",   "阪神"),
    "히로시마 도요 카프":       ("6",   "c",  "carp",     "広島"),
    "세이부 라이온즈":          ("7",   "l",  "lions",    "西武"),
    "니혼햄 파이터즈":          ("8",   "f",  "fighters", "日本ハム"),
    "지바 롯데 마린스":         ("9",   "m",  "marines",  "ロッテ"),
    "오릭스 버팔로즈":          ("11",  "b",  "buffaloes", "オリックス"),
    "소프트뱅크 호크스":        ("12",  "h",  "hawks",    "ソフトバンク"),
    "라쿠텐 골든이글스":        ("376", "e",  "eagles",   "楽天"),
}
YAHOO_ID_TO_KR = {v[0]: k for k, v in TEAMS.items()}


def get(url, **kw):
    time.sleep(SLEEP)
    r = requests.get(url, headers=C.HEADERS, timeout=20, **kw)
    r.encoding = "utf-8"
    return r


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    print(f"[OK] {os.path.relpath(path, BASE)} ({os.path.getsize(path):,} bytes)")


# ----------------------------------------------------------------------------
# 번역 캐시 (collect.translate_text_kr 결과를 파일로 보존)
# ----------------------------------------------------------------------------
TRANS_PATH = os.path.join(CACHE_DIR, "translate.json")
TRANS = load_json(TRANS_PATH, {})


def tr(text):
    if not text:
        return ""
    if text in TRANS:
        return TRANS[text]
    out = C.translate_text_kr(text)
    TRANS[text] = out
    return out


# ----------------------------------------------------------------------------
# 가나 → 한글 (국립국어원 일본어 표기법: 어두 무성음은 예사소리, 어중은 거센소리, 장음 미표기)
# ----------------------------------------------------------------------------
_BASE = {
    "あ": "아", "い": "이", "う": "우", "え": "에", "お": "오",
    "か": ("가", "카"), "き": ("기", "키"), "く": ("구", "쿠"), "け": ("게", "케"), "こ": ("고", "코"),
    "さ": "사", "し": "시", "す": "스", "せ": "세", "そ": "소",
    "た": ("다", "타"), "ち": ("지", "치"), "つ": "쓰", "て": ("데", "테"), "と": ("도", "토"),
    "な": "나", "に": "니", "ぬ": "누", "ね": "네", "の": "노",
    "は": "하", "ひ": "히", "ふ": "후", "へ": "헤", "ほ": "호",
    "ま": "마", "み": "미", "む": "무", "め": "메", "も": "모",
    "や": "야", "ゆ": "유", "よ": "요",
    "ら": "라", "り": "리", "る": "루", "れ": "레", "ろ": "로",
    "わ": "와", "を": "오", "ゐ": "이", "ゑ": "에",
    "が": "가", "ぎ": "기", "ぐ": "구", "げ": "게", "ご": "고",
    "ざ": "자", "じ": "지", "ず": "즈", "ぜ": "제", "ぞ": "조",
    "だ": "다", "ぢ": "지", "づ": "즈", "で": "데", "ど": "도",
    "ば": "바", "び": "비", "ぶ": "부", "べ": "베", "ぼ": "보",
    "ぱ": "파", "ぴ": "피", "ぷ": "푸", "ぺ": "페", "ぽ": "포",
    "ゔ": "부", "ぁ": "아", "ぃ": "이", "ぅ": "우", "ぇ": "에", "ぉ": "오",
    "ゃ": "야", "ゅ": "유", "ょ": "요", "ゎ": "와",
}
_COMBO = {
    "きゃ": ("갸", "캬"), "きゅ": ("규", "큐"), "きょ": ("교", "쿄"),
    "しゃ": "샤", "しゅ": "슈", "しょ": "쇼", "しぇ": "셰",
    "ちゃ": ("자", "차"), "ちゅ": ("주", "추"), "ちょ": ("조", "초"), "ちぇ": ("제", "체"),
    "にゃ": "냐", "にゅ": "뉴", "にょ": "뇨",
    "ひゃ": "햐", "ひゅ": "휴", "ひょ": "효",
    "みゃ": "먀", "みゅ": "뮤", "みょ": "묘",
    "りゃ": "랴", "りゅ": "류", "りょ": "료",
    "ぎゃ": "갸", "ぎゅ": "규", "ぎょ": "교",
    "じゃ": "자", "じゅ": "주", "じょ": "조", "じぇ": "제",
    "びゃ": "뱌", "びゅ": "뷰", "びょ": "뵤",
    "ぴゃ": "퍄", "ぴゅ": "퓨", "ぴょ": "표",
    "ふぁ": "파", "ふぃ": "피", "ふぇ": "페", "ふぉ": "포", "ふゅ": "퓨",
    "てぃ": "티", "でぃ": "디", "とぅ": "투", "どぅ": "두", "でゅ": "듀", "てゅ": "튜",
    "うぃ": "위", "うぇ": "웨", "うぉ": "워", "いぇ": "예", "すぃ": "시", "つぁ": "차",
    "ゔぁ": "바", "ゔぃ": "비", "ゔぇ": "베", "ゔぉ": "보",
    "くぁ": "콰", "くぃ": "퀴", "くぇ": "퀘", "くぉ": "쿼", "ぐぁ": "과", "ぐぃ": "귀", "ぐぇ": "궤", "ぐぉ": "궈",
    "つぃ": "치", "つぇ": "체", "つぉ": "초", "わぉ": "와오", "ゆぇ": "유에",
}
_O_ROW = set("おこごそぞとどのほぼぽもよろをょ")
_U_ROW = set("うくぐすずつづぬふぶぷむゆるゅ")


def _kata2hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def _add_final(syl, jong):
    code = ord(syl) - 0xAC00
    if 0 <= code < 11172 and code % 28 == 0:
        return chr(ord(syl) + jong)
    return syl


def kana_to_hangul(text):
    out_words = []
    for word in re.split(r"[・\s　･=＝]+", _kata2hira(text or "")):
        if not word:
            continue
        res, i, first, prev = [], 0, True, ""
        while i < len(word):
            two, one = word[i:i + 2], word[i]
            if one == "ー":                       # 장음 부호 → 미표기
                i += 1; continue
            if one in "んン":
                if res:
                    res[-1] = _add_final(res[-1], 4)   # ㄴ
                i += 1; continue
            if one in "っッ":
                if res:
                    res[-1] = _add_final(res[-1], 19)  # ㅅ
                i += 1; continue
            # 장모음 생략: お段+う/お, う段+う
            if res and ((one == "う" and (prev in _O_ROW or prev in _U_ROW)) or (one == "お" and prev in _O_ROW)):
                i += 1; prev = one; continue
            if two in _COMBO:
                v = _COMBO[two]; step = 2
            elif one in _BASE:
                v = _BASE[one]; step = 1
            else:
                res.append(one); i += 1; prev = one; first = False; continue
            res.append(v[0] if (isinstance(v, tuple) and first) else (v[1] if isinstance(v, tuple) else v))
            prev = word[i + step - 1]
            i += step; first = False
        out_words.append("".join(res))
    return " ".join(out_words)


KANA_ONLY = re.compile(r"^[぀-ヿ・ー\s　]+$")


# ----------------------------------------------------------------------------
# 지리 정보
# ----------------------------------------------------------------------------
PREFS = load_json(os.path.join(GEO, "prefectures.json"), [])
PREF_BY_SHORT = {p["short"]: p for p in PREFS}
PREF_BY_SHORT.update({p["ja"]: p for p in PREFS})
COUNTRIES = load_json(os.path.join(GEO, "countries.json"), {})
VENUES = {k: v for k, v in load_json(os.path.join(GEO, "venues.json"), {}).items() if not k.startswith("_")}
VENUE_CACHE_PATH = os.path.join(GEO, "venue_cache.json")
VENUE_CACHE = load_json(VENUE_CACHE_PATH, {})


def birthplace_info(raw):
    raw = (raw or "").strip()
    if not raw or raw in ("-", "不明"):
        return {"bp_ja": raw, "bp_ko": "미상", "bp_type": "unknown"}
    p = PREF_BY_SHORT.get(raw) or PREF_BY_SHORT.get(raw.rstrip("都道府県"))
    if p:
        return {"bp_ja": raw, "bp_ko": p["ko"], "bp_type": "pref", "pref_id": p["id"], "region": p["region"]}
    for ja, c in COUNTRIES.items():
        if raw == ja or raw.startswith(ja):
            return {"bp_ja": raw, "bp_ko": c["ko"], "bp_type": "country", "lat": c["lat"], "lon": c["lon"]}
    return {"bp_ja": raw, "bp_ko": tr(raw), "bp_type": "other"}


def geocode_venue(name):
    """지방 구장 좌표: 표 → 캐시 → Nominatim(1초 1회 제한 준수)."""
    if name in VENUES:
        return VENUES[name]
    if name in VENUE_CACHE:
        return VENUE_CACHE[name]
    hit = None
    for q in (f"{name} 野球場", f"{name}球場", f"{name} スタジアム", name):
        try:
            time.sleep(1.1)
            r = requests.get("https://nominatim.openstreetmap.org/search",
                             params={"q": q, "format": "json", "limit": 1, "countrycodes": "jp", "accept-language": "ja"},
                             headers={"User-Agent": "npb-korean-dashboard/1.0 (GitHub Pages hobby project)"}, timeout=15)
            js = r.json() if r.status_code == 200 else []
            if js:
                hit = {"ko": tr(name) if C.JP_RE.search(name) else name,
                       "lat": round(float(js[0]["lat"]), 5), "lon": round(float(js[0]["lon"]), 5),
                       "roof": "open", "geocoded": q, "approx": q == name}
                break
        except Exception as e:
            print(f"[WARN] geocode {q}: {e}")
    VENUE_CACHE[name] = hit or {"ko": tr(name), "lat": None, "lon": None, "roof": "open", "geocoded": None}
    print(f"[GEO] {name} → {VENUE_CACHE[name]}")
    return VENUE_CACHE[name]


# ----------------------------------------------------------------------------
# 1) 시즌 일정 (구단별 월간 달력)
# ----------------------------------------------------------------------------
GAMEKIND_PATH = os.path.join(CACHE_DIR, "game_kind_v2.json")
GAMEKIND = load_json(GAMEKIND_PATH, {})
RESULT_LABEL = {"勝利": "W", "敗戦": "L", "引分": "D", "引き分け": "D"}
CS_RE = re.compile(r"CS([セパ])・(ファースト|ファイナル)ステージ")
JS_RE = re.compile(r"日本シリーズ\s*\d+回戦|日本シリーズ\s*第\d+戦")


def classify_game(gid):
    """경기 페이지로 경기 종류 판별: exhibition(오픈전) / cs / japan_series / regular. 한 번 판별하면 캐시.
    포스트시즌은 페이지 상단의 'CSパ・ファーストステージ 1回戦' 같은 표기로 찾는다."""
    if not gid:
        return "regular"
    if gid in GAMEKIND:
        return GAMEKIND[gid]
    try:
        r = get(f"https://baseball.yahoo.co.jp/npb/game/{gid}/index")
        soup = BeautifulSoup(r.text, "html.parser")
        full = soup.get_text(" ", strip=True)
        head = (soup.title.get_text() if soup.title else "") + " " + full[:1500]
        m = CS_RE.search(full)
        if "オープン戦" in head:
            kind = "exhibition"
        elif JS_RE.search(full):
            kind = "japan_series"
        elif m:
            kind = "cs"
        else:
            kind = "regular"
    except Exception as e:
        print(f"[WARN] classify {gid}: {e}")
        return "regular"          # 실패는 캐시하지 않음
    GAMEKIND[gid] = kind
    return kind


def parse_month(team_kr, yid, year, month):
    r = get(f"https://baseball.yahoo.co.jp/npb/teams/{yid}/schedule", params={"month": f"{year}-{month:02d}"})
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    sel = soup.select_one(".bb-scheduleNavi__item--selected")
    if not sel or sel.get_text(strip=True) != f"{month}月":
        return []                 # 없는 달을 요청하면 Yahoo가 다른 달을 보여줌 → 무시
    games = []
    for td in soup.select("td.bb-calendarTable__data"):
        d_el = td.select_one(".bb-calendarTable__date")
        opp_a = td.select_one(".bb-calendarTable__teamName a")
        if not d_el or not opp_a:
            continue
        try:
            day = int(re.sub(r"\D", "", d_el.get_text()))
        except ValueError:
            continue
        m = re.search(r"/npb/teams/(\d+)/", opp_a.get("href", ""))
        opp = (YAHOO_ID_TO_KR.get(m.group(1)) if m else None) or C.team_kr(opp_a.get_text(strip=True))
        is_home = "--home" in " ".join(td.get("class", []))
        venue = (td.select_one(".bb-calendarTable__venue") or BeautifulSoup("", "html.parser")).get_text(strip=True)
        st_a = td.select_one("a.bb-calendarTable__status")
        status_raw = st_a.get_text(strip=True) if st_a else ""
        gm = re.search(r"/npb/game/(\d+)/", st_a.get("href", "")) if st_a else None
        gid = gm.group(1) if gm else ""
        sc = td.select_one(".bb-calendarTable__score")
        # 점수는 '홈팀 점수 - 원정팀 점수' 순서, 승패 아이콘(aria-label)은 이 팀 기준
        h_el = sc.select_one(".bb-calendarTable__home") if sc else None
        a_el = sc.select_one(".bb-calendarTable__away") if sc else None
        hs = h_el.get_text(strip=True) if h_el else ""
        as_ = a_el.get_text(strip=True) if a_el else ""
        icon = sc.select_one("[aria-label]") if sc else None
        label = icon.get("aria-label", "") if icon else ""
        state = C.game_state(status_raw)
        if label == "ノーゲーム" or (sc and sc.select_one(".bb-calendarTable__nogame")):
            state = "cancel"
        result = RESULT_LABEL.get(label, "") if state == "final" else ""
        my, op = (hs, as_) if is_home else (as_, hs)
        kind = classify_game(gid) if month in (2, 3, 10, 11) else "regular"
        games.append({"date": f"{year}-{month:02d}-{day:02d}", "opp": opp, "home": is_home, "venue": venue,
                      "my": my, "op": op, "state": state, "result": result, "kind": kind, "gid": gid})
    return games


def fetch_season():
    year = C.SEASON
    teams, venues = {}, {}
    for kr, (yid, _, code, _) in TEAMS.items():
        games = []
        for month in range(3, 12):
            try:
                games += parse_month(kr, yid, year, month)
            except Exception as e:
                print(f"[ERROR] season {kr} {month}: {e}")
        seen, uniq = set(), []
        for g in games:
            if g["kind"] == "exhibition":     # 오픈전(시범경기)은 분석에서 제외
                continue
            key = g["gid"] or (g["date"], g["opp"], g["venue"])
            if key not in seen:
                seen.add(key); uniq.append(g)
        uniq.sort(key=lambda g: g["date"])
        teams[kr] = uniq
        for g in uniq:
            if g["venue"] and g["venue"] not in venues:
                venues[g["venue"]] = geocode_venue(g["venue"])
        print(f"[OK] {kr} 시즌 {len(uniq)}경기")
    save_json(VENUE_CACHE_PATH, VENUE_CACHE)
    save_json(GAMEKIND_PATH, GAMEKIND, compact=True)
    return {"season": year, "updated_at": C.now_jst().strftime("%Y-%m-%d %H:%M"),
            "venues": venues, "teams": teams}


# ----------------------------------------------------------------------------
# 2) 선수 프로필
# ----------------------------------------------------------------------------
POS_KR = {"投手": "투수", "捕手": "포수", "内野手": "내야수", "外野手": "외야수"}
HAND_KR = {"右": "우", "左": "좌", "両": "양"}


def hand_kr(s):
    m = re.match(r"(右|左|両)投(右|左|両)打", s or "")
    return f"{HAND_KR[m.group(1)]}투{HAND_KR[m.group(2)]}타" if m else (s or "")


def draft_kr(s):
    s = (s or "").strip()
    if not s or s == "-":
        return ""
    y = re.search(r"(\d{4})年", s)
    rank = re.search(r"(\d+)位", s)
    ikusei = "育" in s
    if y and rank:
        return f"{y.group(1)}년 {'육성 ' if ikusei else ''}{rank.group(1)}순위"
    if "自由" in s:
        return f"{y.group(1) if y else ''}년 자유획득".strip()
    return tr(s)


SCHOOL_SUFFIX = [            # (일본어 접미사, 한국어) - 긴 것부터
    ("高等学校", "고"), ("高校", "고"), ("短期大学", "단대"), ("短大", "단대"), ("大学院", "대학원"),
    ("大学", "대"), ("専門学校", "전문학교"), ("高専", "고전"), ("中学校", "중"), ("大", "대"), ("高", "고"),
]


def split_school(seg):
    """'東海大相模高（甲）' → ('東海大相模', '고', True)  /  'トヨタ自動車' → ('トヨタ自動車', '', False)"""
    koshien = bool(re.search(r"[（(]甲[）)]", seg))
    core = re.sub(r"[（(][^）)]*[）)]", "", seg).strip()
    for ja, ko in SCHOOL_SUFFIX:
        if core.endswith(ja) and len(core) > len(ja):
            return core[:-len(ja)], ko, koshien
    return core, "", koshien


def career_kr(s):
    """경력 구간만 나눠 두고, 번역은 fill_career_ko()에서 구단 단위로 일괄 처리."""
    segs = [x.strip() for x in re.split(r"[－\-–—]", s or "") if x.strip()]
    return [{"ja": x, "ko": ""} for x in segs]


SUFFIX_FULL_JA = {"고": "高校", "대": "大学", "단대": "短期大学", "대학원": "大学院", "전문학교": "専門学校", "고전": "高専", "중": "中学校"}
SUFFIX_KO_RE = {
    "고": r"\s*(고등학교|고교|고)$", "대": r"\s*(대학교|대학|대)$", "단대": r"\s*(단기대학|단대)$",
    "대학원": r"\s*대학원$", "전문학교": r"\s*전문학교$", "고전": r"\s*(고등전문학교|고전)$", "중": r"\s*(중학교|중)$",
}


def _school_query(stem, suf):
    """번역기에 보낼 문구: 이름만 보내면 뜻으로 번역(白鴎→흰오리)되므로 '白鴎大学'처럼 학교 종류까지 붙여 고유명사로 인식시킴."""
    return stem + SUFFIX_FULL_JA.get(suf, "")


def _school_ko(stem, suf, translated):
    t = (translated or "").strip()
    if suf and suf in SUFFIX_KO_RE:
        t = re.sub(SUFFIX_KO_RE[suf], "", t).strip()
    t = t.replace(" ", "") if len(t) <= 10 else t
    return t + suf if t else ""


# ----------------------------------------------------------------------------
# 학교명: 뜻 번역 대신 일본어 발음을 한글로 (慶應義塾 → 게이오기주쿠)
#   읽기는 형태소 분석기 MeCab(unidic-lite)으로, 사전에 없는 말은 pykakasi로 보완
# ----------------------------------------------------------------------------
# 읽기 보정: 형태소 분석기가 인명·지명으로 잘못 읽는 학교명
STEM_READING = {      # 학교명 어간 전체
    "社": "やしろ", "仁川学院": "にがわがくいん", "明豊": "めいほう", "必由館": "ひつゆうかん",
    "亜細亜": "あじあ", "星槎道都": "せいさどうと", "履正社": "りせいしゃ",
}
PART_READING = {"智辯": "ちべん", "智弁": "ちべん", "明徳": "めいとく", "光星": "こうせい"}   # 어간 속 일부
TOKEN_READING = {"付": "ふ", "附": "ふ"}                                               # 형태소 하나
HANGUL_OVERRIDE = {"亜細亜": "아시아"}                                                  # 최종 한글 (관용 표기)
_TAGGER, _KAKASI = None, None


def _reading_tools():
    global _TAGGER, _KAKASI
    if _TAGGER is None:
        try:
            from fugashi import Tagger
            import pykakasi
            _TAGGER, _KAKASI = Tagger(), pykakasi.kakasi()
        except Exception as e:
            print(f"[WARN] 읽기 분석기 없음 ({e}) → 학교명은 번역으로 대체")
            _TAGGER = False
    return _TAGGER, _KAKASI


def _kakasi(text):
    return "".join(x["hira"] for x in _KAKASI.convert(text))


def reading_parts(text):
    """일본어 고유명사 → 형태소별 읽기 목록. 분석기가 모르는 말이 섞이면 전체를 pykakasi로 읽는다."""
    tagger, _ = _reading_tools()
    if not tagger:
        return []
    if text in STEM_READING:
        return [STEM_READING[text]]
    # 보정할 부분 문자열을 기준으로 나눠서 따로 읽기
    for part, rd in sorted(PART_READING.items(), key=lambda x: -len(x[0])):
        if part in text and part != text:
            i = text.index(part)
            return reading_parts(text[:i]) + [rd] + reading_parts(text[i + len(part):]) if text[:i] or text[i + len(part):] else [rd]
    if text in PART_READING:
        return [PART_READING[text]]
    parts, unknown = [], False
    for w in tagger(text):
        surf = w.surface
        if surf in TOKEN_READING:
            parts.append(TOKEN_READING[surf]); continue
        if not C.JP_RE.search(surf):
            parts.append(surf); continue
        kana = getattr(w.feature, "kana", None)
        if not kana or kana == "*":
            unknown = True
            break
        parts.append(kana)
    return [_kakasi(text)] if unknown else parts


def school_ko(stem, suf):
    """학교명 어간의 일본어 발음 한글 표기 + 학교 종류. 예) 慶應義塾 + 대 → 게이오기주쿠대, 大阪桐蔭 + 고 → 오사카도인고
    형태소마다 따로 한글로 옮겨(각각 첫소리 규칙 적용) 붙여 쓴다."""
    key = "R2:" + stem
    if key not in TRANS:
        if stem in HANGUL_OVERRIDE:
            TRANS[key] = HANGUL_OVERRIDE[stem]
        else:
            parts = reading_parts(stem)
            if not parts:
                return ""
            TRANS[key] = "".join(p if not C.JP_RE.search(p) else kana_to_hangul(p).replace(" ", "") for p in parts)
    return TRANS[key] + suf if TRANS[key] else ""


def fill_career_ko(players):
    """경력 구간 한국어화: 학교는 일본어 발음 그대로 한글로(+고/대), 그 밖의 소속은 팀명 변환·번역. 실패한 것은 다음 실행에서 재시도."""
    for p in players:
        for c in p.get("career", []):
            stem, suf, koshien = split_school(c["ja"])
            c["koshien"] = koshien
            if suf and C.JP_RE.search(stem):
                ko = school_ko(stem, suf)
                if ko:
                    c["ko"] = ko
                    c["school"] = True
    _fill_career_translate([c for p in players for c in p.get("career", []) if not c.get("school")])


def _fill_career_translate(items):
    """학교가 아닌 경력(구단·실업팀 등): 번역 캐시 사용."""
    players = [{"career": items}]
    queries = {}
    for p in players:
        for c in p.get("career", []):
            stem, suf, _ = split_school(c["ja"])
            if not C.JP_RE.search(C._replace_teams(stem)):
                continue
            q = _school_query(stem, suf)
            if "S2:" + q not in TRANS:
                queries[q] = (stem, suf)
    if queries:
        got = C.translate_batch_kr(sorted(queries))
        for q, v in got.items():
            stem, suf = queries[q]
            TRANS["S2:" + q] = _school_ko(stem, suf, v)
        print(f"[TR] 학교·소속 {len(queries)}개 중 {len(got)}개 번역")
    for p in players:
        for c in p.get("career", []):
            stem, suf, _ = split_school(c["ja"])
            base = C._replace_teams(stem)
            if C.JP_RE.search(base):
                c["ko"] = TRANS.get("S2:" + _school_query(stem, suf), "") or c.get("ko", "")
            else:
                c["ko"] = base + suf


KANA_RUN = re.compile(r"[぀-ヿー・]+")


def clean_name(name):
    """사전 항목에 섞여 있는 가나(예: '린 쿠ァ첸')를 한글로 정리."""
    name = (name or "").replace("・", " ").replace("･", " ")
    name = re.sub(r"\s{2,}", " ", KANA_RUN.sub(lambda m: kana_to_hangul(m.group(0)).replace(" ", ""), name)).strip()
    return C.drop_long_vowels(name)


def refresh_translations():
    """이미 저장된 프로필의 이름·경력 번역을 보완 (새로 크롤링하지 않음)."""
    idx = load_json(os.path.join(PROF_DIR, "index.json"), {"teams": {}})
    for kr, t in idx.get("teams", {}).items():
        path = os.path.join(PROF_DIR, f"{t['code']}.json")
        d = load_json(path, None)
        if not d:
            continue
        before = json.dumps(d, ensure_ascii=False)
        for p in d["players"]:
            if C.JP_RE.search(p.get("name", "")):
                p["name"] = clean_name(p["name"])
        fill_career_ko(d["players"])
        if json.dumps(d, ensure_ascii=False) != before:
            save_json(path, d, compact=True)


def npb_kana_map(npb_code):
    """npb.jp 명단에서 이름 → 읽기(가나). 번역 사전에 없는 선수만 쓴다."""
    out = {}
    try:
        r = get(f"https://npb.jp/bis/teams/rst_{npb_code}.html")
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("table.rosterlisttbl a[href*='/bis/players/']"):
            out[re.sub(r"[\s　]", "", a.get_text())] = "https://npb.jp" + a["href"]
    except Exception as e:
        print(f"[WARN] npb roster {npb_code}: {e}")
    return out


def npb_reading(url):
    try:
        r = get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        name = soup.select_one("#pc_v_name")
        if name:
            parts = name.get_text("|", strip=True).split("|")
            for p in parts:
                if KANA_ONLY.match(p) and "・" in p:
                    return p
    except Exception as e:
        print(f"[WARN] npb reading {url}: {e}")
    return ""


def name_kr(jp, npb_links):
    clean = re.sub(r"[\s　]", "", jp)
    hit = C.PLAYER_NAME_TRANSLATION.get(clean)
    if hit:
        return clean_name(re.split(r"[（(]", hit)[0].strip()), "dict"
    if KANA_ONLY.match(jp.replace(" ", "")):
        return kana_to_hangul(jp), "kana"
    url = npb_links.get(clean)
    if url:
        reading = npb_reading(url)
        if reading:
            return kana_to_hangul(reading), "reading"
    return tr(jp), "mt"


def parse_player(url):
    r = get(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    g = lambda sel: (soup.select_one(sel).get_text(strip=True) if soup.select_one(sel) else "")
    prof = {}
    for item in soup.select("dl.bb-profile__list .bb-profile__item"):
        k = item.select_one(".bb-profile__title"); v = item.select_one(".bb-profile__text")
        if k and v:
            prof[k.get_text(strip=True)] = v.get_text(" ", strip=True)
    name = g(".bb-profile__name")
    if not name:
        return None
    birth_raw = prof.get("生年月日（満年齢）", "")
    bm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", birth_raw)
    age = re.search(r"（(\d+)歳）", birth_raw)
    num = g(".bb-profile__number")
    return {
        "id": re.search(r"/player/(\d+)/", url).group(1),
        "name_jp": name, "no": num,
        "ikusei": num.isdigit() and int(num) >= 100,
        "pos": POS_KR.get(g(".bb-profile__position")) or tr(g(".bb-profile__position")),
        "birth": f"{bm.group(1)}-{int(bm.group(2)):02d}-{int(bm.group(3)):02d}" if bm else "",
        "age": int(age.group(1)) if age else None,
        "height": int(re.sub(r"\D", "", prof.get("身長", "")) or 0) or None,
        "weight": int(re.sub(r"\D", "", prof.get("体重", "")) or 0) or None,
        "blood": prof.get("血液型", "").replace("不明", "") or "",
        "hand": hand_kr(prof.get("投打", "")),
        "draft": draft_kr(prof.get("ドラフト年（順位）", "")),
        "years": int(re.sub(r"\D", "", prof.get("プロ通算年", "")) or 0) or None,
        "career": career_kr(prof.get("経歴", "")),
        **birthplace_info(prof.get("出身地", "")),
        "url": url,
    }


def stale_teams(force=False):
    idx = load_json(os.path.join(PROF_DIR, "index.json"), {"teams": {}})
    out = []
    for kr in TEAMS:
        t = idx.get("teams", {}).get(kr, {})
        try:
            age = (C.now_jst() - datetime.datetime.strptime(t["updated_at"], "%Y-%m-%d %H:%M").replace(tzinfo=C.JST)).days
        except Exception:
            age = 999
        if force or age >= PROFILE_MAX_AGE_DAYS:
            out.append((age, kr))
    return [kr for _, kr in sorted(out, key=lambda x: -x[0])]     # 오래된 구단부터


def fetch_profiles(force=False):
    os.makedirs(PROF_DIR, exist_ok=True)
    idx_path = os.path.join(PROF_DIR, "index.json")
    index = load_json(idx_path, {"teams": {}})
    index.setdefault("teams", {})
    todo = stale_teams(force)
    print(f"[PROFILE] 갱신 대상 {len(todo)}개 구단: {', '.join(todo)}")
    for kr in todo:
        if time_left() < 6 * 60:
            print(f"[STOP] 시간 예산 소진 → 남은 구단은 다음 실행에서: {kr} ...")
            break
        yid, npb_code, code, _ = TEAMS[kr]
        try:
            r = get(f"https://baseball.yahoo.co.jp/npb/teams/{yid}/players")
            links = []
            for a_ in BeautifulSoup(r.text, "html.parser").find_all("a", href=True):
                m = re.search(r"/npb/player/(\d+)/top", a_["href"])
                if m and m.group(0) not in links:
                    links.append(m.group(0))
            npb_links = npb_kana_map(npb_code)
            players, t0 = [], time.time()
            for path in links:
                try:
                    p = parse_player("https://baseball.yahoo.co.jp" + path)
                    if not p:
                        continue
                    p["name"], p["name_src"] = name_kr(p["name_jp"], npb_links)
                    players.append(p)
                except Exception as e:
                    print(f"[WARN] player {path}: {e}")
            fill_career_ko(players)
            players.sort(key=lambda p: (int(p["no"]) if p["no"].isdigit() else 9999))
            now = C.now_jst().strftime("%Y-%m-%d %H:%M")
            save_json(os.path.join(PROF_DIR, f"{code}.json"),
                      {"team": kr, "updated_at": now, "players": players}, compact=True)
            src = {}
            for p in players:
                src[p["name_src"]] = src.get(p["name_src"], 0) + 1
            index["teams"][kr] = {"code": code, "count": len(players), "updated_at": now}
            index["updated_at"] = now
            save_json(idx_path, index)
            save_json(TRANS_PATH, TRANS, compact=True)   # 중간 저장
            print(f"[OK] {kr} 선수 {len(players)}명 ({time.time() - t0:.0f}초, 이름 출처 {src})")
        except Exception as e:
            print(f"[ERROR] profiles {kr}: {e}")


def main():
    args = sys.argv[1:]
    print(f"=== 공간분석 데이터 수집 ({C.now_jst():%Y-%m-%d %H:%M} JST, 시간 예산 {TIME_BUDGET_MIN:.0f}분) ===")
    if "--profiles-only" not in args:
        save_json(os.path.join(DATA, "season.json"), fetch_season(), compact=True)
    if "--season-only" not in args:
        fetch_profiles(force="--profiles" in args)
        refresh_translations()
    save_json(TRANS_PATH, TRANS, compact=True)


if __name__ == "__main__":
    main()
