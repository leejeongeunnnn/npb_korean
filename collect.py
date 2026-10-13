# -*- coding: utf-8 -*-
"""
NPB 정적 대시보드용 데이터 수집 스크립트.

GitHub Actions가 주기적으로 이 스크립트를 실행하면 data/ 폴더에
JSON 파일들이 갱신되고, index.html(순수 HTML/JS)이 그 JSON을 읽어
Streamlit 없이 GitHub Pages만으로 대시보드를 표시한다.

수집 항목:
  - data/standings.json   리그 순위 (센트럴/퍼시픽)
  - data/schedule.json    최근 30일 경기 일정/결과
  - data/postseason.json  포스트시즌(CS·일본시리즈) 마스터 일정 + 실시간 경기
  - data/batters.json     규정타석 타자 성적
  - data/news.json        금일 야구 기사 요약(한국어)
  - data/meta.json        마지막 갱신 시각

teams.json(팀 소개·구장)은 자주 바뀌지 않으므로 저장소에 고정 포함한다.
"""

import os
import re
import json
import html
import datetime
import urllib.parse

import requests
from bs4 import BeautifulSoup

try:
    # 저장소에 포함된 선수 이름 번역 사전 재사용
    from player_translations import PLAYER_NAME_TRANSLATION
except Exception:
    PLAYER_NAME_TRANSLATION = {}

# ----------------------------------------------------------------------------
# 설정
# ----------------------------------------------------------------------------
SEASON = int(os.environ.get("NPB_SEASON", "2026"))
SCHEDULE_DAYS_BACK = 23   # 오늘 기준 과거 일수
SCHEDULE_DAYS_FWD = 6     # 오늘 기준 미래 일수  (합계 30일)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0 Safari/537.36"
}

JST = datetime.timezone(datetime.timedelta(hours=9))


def now_jst():
    return datetime.datetime.now(JST)


# ----------------------------------------------------------------------------
# 팀 기본 정보
# ----------------------------------------------------------------------------
TEAM_INFO = {
    "巨人":       {"kr": "요미우리 자이언츠",        "color": "#F97316"},
    "阪神":       {"kr": "한신 타이거스",            "color": "#EAB308"},
    "中日":       {"kr": "주니치 드래곤즈",          "color": "#3B82F6"},
    "DeNA":       {"kr": "요코하마 DeNA 베이스타스", "color": "#2563EB"},
    "ヤクルト":   {"kr": "야쿠르트 스왈로스",        "color": "#475569"},
    "広島":       {"kr": "히로시마 도요 카프",       "color": "#EF4444"},
    "ソフトバンク": {"kr": "소프트뱅크 호크스",       "color": "#FBBF24"},
    "オリックス": {"kr": "오릭스 버팔로즈",          "color": "#1E293B"},
    "ロッテ":     {"kr": "지바 롯데 마린스",         "color": "#94A3B8"},
    "楽天":       {"kr": "라쿠텐 골든이글스",        "color": "#991B1B"},
    "西武":       {"kr": "세이부 라이온즈",          "color": "#2563EB"},
    "日本ハム":   {"kr": "니혼햄 파이터즈",          "color": "#06B6D4"},
}

TEAM_SEARCH_KEYWORDS = {
    "소프트뱅크 호크스": "福岡ソフトバンクホークス",
    "오릭스 버팔로즈": "オリックス・バファローズ",
    "지바 롯데 마린스": "千葉ロッテマリーンズ",
    "라쿠텐 골든이글스": "東北楽天ゴールデンイーグルス",
    "세이부 라이온즈": "埼玉西武ライオンズ",
    "니혼햄 파이터즈": "北海道日本ハムファイターズ",
    "한신 타이거스": "阪神タイガース",
    "요미우리 자이언츠": "読売ジャイアンツ",
    "요코하마 DeNA 베이스타스": "横浜DeNAベイスターズ",
    "히로시마 도요 카프": "広島東洋カープ",
    "야쿠르트 스왈로스": "東京ヤクルトスワローズ",
    "주니치 드래곤즈": "中日ドラゴンズ",
}


def translate_player_name(jp_name):
    if not jp_name:
        return jp_name
    clean = jp_name.replace(" ", "").replace("　", "").replace("\xa0", "")
    return PLAYER_NAME_TRANSLATION.get(clean, jp_name)


# ----------------------------------------------------------------------------
# 일본어 -> 한국어 간이 번역 (야구 용어 사전 + 선택적 무료 번역 API)
# ----------------------------------------------------------------------------
BASEBALL_TERMS = {
    "クライマックスシリーズ": "클라이맥스 시리즈",
    "クライマックス": "클라이맥스",
    "ファーストステージ": "퍼스트 스테이지",
    "ファイナルステージ": "파이널 스테이지",
    "日本シリーズ": "일본시리즈",
    "セ・リーグ": "센트럴 리그",
    "パ・リーグ": "퍼시픽 리그",
    "セリーグ": "센트럴 리그",
    "パリーグ": "퍼시픽 리그",
    "ドラフト会議": "드래프트 회의",
    "ドラフト": "드래프트",
    "スカウト": "스카우트",
    "指名": "지명",
    "高校生": "고교생",
    "大学生": "대학생",
    "社会人": "사회인 야구",
    "戦力外通告": "전력외 통고(방출)",
    "戦力外": "전력외 통고",
    "現役ドラフト": "현역 드래프트",
    "自由契約": "자유계약",
    "引退": "은퇴",
    "退任": "퇴임",
    "退団": "퇴단",
    "解任": "해임",
    "就任": "취임",
    "去就": "거취",
    "トレード": "트레이드",
    "契約更改": "계약 갱신",
    "契約": "계약",
    "残留": "잔류",
    "移籍": "이적",
    "秋季キャンプ": "가을 마무리 캠프",
    "キャンプ": "캠프",
    "自主トレ": "개인 훈련",
    "実戦": "실전",
    "打撃練習": "타격 훈련",
    "監督": "감독",
    "コーチ": "코치",
    "新人王": "신인왕",
    "本塁打": "홈런",
    "満塁": "만루",
    "サヨナラ": "끝내기",
    "完封": "완봉",
    "完投": "완투",
    "勝利": "승리",
    "敗戦": "패전",
    "優勝": "우승",
    "逆転": "역전",
    "先発": "선발",
    "救援": "구원",
    "投手": "투수",
    "打者": "타자",
    "打点": "타점",
    "盗塁": "도루",
    "三振": "삼진",
    "四球": "볼넷",
    "王手": "리치(매치포인트)",
    "突破": "돌파",
    "進出": "진출",
    "対戦": "맞대결",
    "球団": "구단",
    "選手": "선수",
    "試合": "경기",
    "開幕": "개막",
}

_TRANS_CACHE = {}
JP_RE = re.compile(r"[぀-ヿ一-鿿]")

# 팀명 치환 순서: 정식명칭 → 애칭 → 약칭 (긴 것부터 치환해야 "주니치 드래곤즈ドラゴンズ" 같은 중복이 안 생김)
TEAM_NAME_REPLACE = [
    ("読売ジャイアンツ", "요미우리 자이언츠"), ("阪神タイガース", "한신 타이거스"),
    ("中日ドラゴンズ", "주니치 드래곤즈"), ("横浜DeNAベイスターズ", "요코하마 DeNA 베이스타스"),
    ("東京ヤクルトスワローズ", "야쿠르트 스왈로스"), ("広島東洋カープ", "히로시마 도요 카프"),
    ("福岡ソフトバンクホークス", "소프트뱅크 호크스"), ("オリックス・バファローズ", "오릭스 버팔로즈"),
    ("千葉ロッテマリーンズ", "지바 롯데 마린스"), ("東北楽天ゴールデンイーグルス", "라쿠텐 골든이글스"),
    ("埼玉西武ライオンズ", "세이부 라이온즈"), ("北海道日本ハムファイターズ", "니혼햄 파이터즈"),
    ("ジャイアンツ", "자이언츠"), ("タイガース", "타이거스"), ("ドラゴンズ", "드래곤즈"),
    ("ベイスターズ", "베이스타스"), ("スワローズ", "스왈로스"), ("カープ", "카프"),
    ("ホークス", "호크스"), ("バファローズ", "버팔로즈"), ("マリーンズ", "마린스"),
    ("イーグルス", "이글스"), ("ライオンズ", "라이온즈"), ("ファイターズ", "파이터즈"),
    ("日本ハム", "니혼햄"), ("ソフトバンク", "소프트뱅크"), ("オリックス", "오릭스"),
    ("ヤクルト", "야쿠르트"), ("ロッテ", "롯데"), ("巨人", "요미우리"), ("阪神", "한신"),
    ("中日", "주니치"), ("広島", "히로시마"), ("楽天", "라쿠텐"), ("西武", "세이부"),
]


def _replace_teams(text):
    for jp, ko in TEAM_NAME_REPLACE:
        text = text.replace(jp, ko)
    # 기사에서 소프트뱅크를 'ソフト'로 줄여 쓰는 경우 (소프트웨어로 오역 방지)
    text = re.sub(r"ソフト(?!ウェア|ボール|クリーム)", "소프트뱅크", text)
    # 일본 기사식 괄호 【구단】 → [구단]
    text = text.replace("【", "[").replace("】", "] ")
    return text


def _tidy(text):
    text = re.sub(r"\[\s*\]|\(\s*\)|「\s*」", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()


# 번역기 차단기: 연속으로 실패하면 이번 실행에서는 더 부르지 않는다 (타임아웃 누적 방지)
_BREAKER = {"_google_translate": 0, "_mymemory_translate": 0}
_BREAKER_LIMIT = 4


def _google_translate(text):
    """키가 필요 없는 Google 번역 공개 엔드포인트 (POST: 여러 줄을 한 번에 보낼 수 있음)."""
    url = "https://translate.googleapis.com/translate_a/single"
    params = {"client": "gtx", "sl": "ja", "tl": "ko", "dt": "t"}
    res = requests.post(url, params=params, data={"q": text}, headers=HEADERS, timeout=6)
    res.raise_for_status()
    data = res.json()
    return "".join(seg[0] for seg in data[0] if seg and seg[0])


def _mymemory_translate(text):
    api = ("https://api.mymemory.translated.net/get?q="
           + urllib.parse.quote(text[:450]) + "&langpair=ja|ko")
    res = requests.get(api, timeout=5)
    res.raise_for_status()
    t = res.json().get("responseData", {}).get("translatedText", "")
    if not t or "MYMEMORY WARNING" in t.upper():
        raise ValueError("mymemory quota")
    return html.unescape(t)


def _call_translators(text, allow=("_google_translate", "_mymemory_translate")):
    for name in ("_google_translate", "_mymemory_translate"):
        if name not in allow or _BREAKER[name] >= _BREAKER_LIMIT:
            continue
        fn = globals()[name]
        try:
            out = fn(text)
            if out:
                _BREAKER[name] = 0
                return out
        except Exception as e:
            _BREAKER[name] += 1
            print(f"[WARN] 번역 실패({name}, 연속 {_BREAKER[name]}회): {str(e)[:120]}")
            if _BREAKER[name] >= _BREAKER_LIMIT:
                print(f"[WARN] {name} 차단: 이번 실행에서는 더 이상 호출하지 않음")
    return None


def translate_text_kr(text, use_api=True):
    """일본어 → 한국어. 팀명을 먼저 한국어로 고정한 뒤 번역기 사용,
    번역기가 모두 실패하면 야구 용어 사전으로 최대한 치환."""
    if not text:
        return ""
    if text in _TRANS_CACHE:
        return _TRANS_CACHE[text]

    clean = _replace_teams(text)
    translated = False
    if JP_RE.search(clean) and use_api:
        out = _call_translators(clean)
        if out:
            clean, translated = out, True

    if JP_RE.search(clean):  # 번역기 실패 시 사전 치환
        for jp, ko in BASEBALL_TERMS.items():
            clean = clean.replace(jp, ko)

    clean = _tidy(clean)
    if translated or not JP_RE.search(clean):
        _TRANS_CACHE[text] = clean      # 번역에 실패한 것은 캐시하지 않음 → 다음 실행에서 재시도
    return clean


def translate_batch_kr(texts, chunk_chars=1500):
    """여러 문구를 줄바꿈으로 묶어 한 번에 번역. {원문: 번역} 반환 (실패한 항목은 빠짐)."""
    out, todo = {}, [t for t in dict.fromkeys(texts) if t]
    i = 0
    while i < len(todo):
        chunk, size = [], 0
        while i < len(todo) and (size + len(todo[i]) + 1 <= chunk_chars or not chunk):
            chunk.append(todo[i]); size += len(todo[i]) + 1; i += 1
        src = [_replace_teams(t) for t in chunk]
        res = _call_translators("\n".join(src), allow=("_google_translate",))
        lines = res.split("\n") if res else []
        if len(lines) == len(chunk):
            for t, l in zip(chunk, lines):
                out[t] = _tidy(l.strip())
        elif res is not None and len(chunk) > 1:
            # 줄 수가 어긋나면 반으로 나눠 다시 시도
            half = len(chunk) // 2
            out.update(translate_batch_kr(chunk[:half], chunk_chars))
            out.update(translate_batch_kr(chunk[half:], chunk_chars))
        if res is None and _BREAKER["_google_translate"] >= _BREAKER_LIMIT:
            break
    return out


# ----------------------------------------------------------------------------
# 경기 데이터 한국어 변환 (팀 약칭 / 구장 약칭 / 경기 상태)
# ----------------------------------------------------------------------------
VENUE_KR = {
    "東京ドーム": "도쿄 돔", "甲子園": "한신 고시엔 구장", "京セラD大阪": "교세라 돔 오사카",
    "京セラドーム": "교세라 돔 오사카", "バンテリンドーム": "반테린 돔 나고야",
    "バンテリン": "반테린 돔 나고야", "横浜": "요코하마 스타디움", "神宮": "메이지 진구 야구장",
    "マツダスタジアム": "마쓰다 스타디움", "マツダ": "마쓰다 스타디움",
    "みずほPayPay": "미즈호 PayPay 돔", "PayPayドーム": "미즈호 PayPay 돔",
    "ZOZOマリン": "조조 마린 스타디움", "楽天モバイル": "라쿠텐 모바일 파크",
    "ベルーナドーム": "벨루나 돔", "ベルーナ": "벨루나 돔",
    "エスコンF": "에스콘 필드 홋카이도", "エスコン": "에스콘 필드 홋카이도",
    "ほっと神戸": "홋토못토 필드 고베", "倉敷": "구라시키", "那覇": "나하",
    "沖縄セルラー": "오키나와 셀룰러 파크 나하", "富山": "도야마", "岐阜": "기후",
    "函館": "하코다테", "旭川": "아사히카와", "釧路": "구시로", "松山": "마쓰야마",
    "北九州": "기타큐슈", "鹿児島": "가고시마", "熊本": "구마모토", "長崎": "나가사키",
    "宇都宮": "우쓰노미야", "福島": "후쿠시마", "前橋": "마에바시", "静岡": "시즈오카",
    "浜松": "하마마쓰", "金沢": "가나자와", "新潟": "니가타", "秋田": "아키타", "盛岡": "모리오카",
    "山形": "야마가타", "郡山": "고리야마", "いわき": "이와키", "大宮": "오미야", "県営大宮": "현영 오미야 구장",
}

STATUS_KR = {
    "試合終了": "경기 종료", "試合中": "진행 중", "試合前": "경기 전",
    "試合中止": "경기 취소(우천 등)", "予告先発": "선발 예고", "ノーゲーム": "노게임",
    "サスペンデッド": "서스펜디드", "見どころ": "경기 전", "中止": "경기 취소",
}


def team_kr(name):
    if not name:
        return name
    info = TEAM_INFO.get(name.strip())
    if info:
        return info["kr"]
    return _replace_teams(name)


def venue_kr(name):
    if not name:
        return ""
    name = name.strip()
    if name in VENUE_KR:
        return VENUE_KR[name]
    for jp, ko in VENUE_KR.items():
        if jp in name:
            return ko
    return translate_text_kr(name) if JP_RE.search(name) else name


def game_state(label):
    """경기 상태 코드: live(진행 중) / final(종료) / cancel(취소) / pre(시작 전)."""
    label = (label or "").strip()
    if "試合終了" in label or label == "終了":
        return "final"
    if any(k in label for k in ("中止", "ノーゲーム", "サスペンデッド")):
        return "cancel"
    if re.search(r"\d+回", label) or "試合中" in label:
        return "live"
    return "pre"


def status_kr(label):
    """'試合終了' → '경기 종료', '7回表' → '7회초', '18:00' 그대로."""
    if not label:
        return ""
    label = label.strip()
    if label in STATUS_KR:
        return STATUS_KR[label]
    m = re.match(r"^(\d+)回(表|裏)", label)
    if m:
        return f"{m.group(1)}회{'초' if m.group(2) == '表' else '말'} 진행 중"
    if re.match(r"^\d{1,2}:\d{2}$", label):
        return f"{label} 시작"
    for jp, ko in STATUS_KR.items():
        if jp in label:
            return ko
    return translate_text_kr(label) if JP_RE.search(label) else label


# ----------------------------------------------------------------------------
# 1) 리그 순위
# ----------------------------------------------------------------------------
def fetch_standings():
    url = "https://baseball.yahoo.co.jp/npb/standings/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")
        tables = soup.find_all("table", class_="bb-rankTable")
        if len(tables) < 2:
            return {"central": [], "pacific": []}

        def parse(table):
            teams, first_w, first_l = [], None, None
            for r in table.find_all("tr"):
                tds = r.find_all("td")
                if len(tds) < 8:
                    continue
                rank_raw = tds[0].text.strip()
                rank = "1위" if rank_raw in ["優勝", "1"] else f"{rank_raw}위"
                name = (tds[1].find("a").text.strip()
                        if tds[1].find("a") else tds[1].text.strip())
                games = tds[2].text.strip()
                wins = tds[3].text.strip()
                losses = tds[4].text.strip()
                draws = tds[5].text.strip()
                pct = tds[6].text.strip()
                raw_diff = tds[7].text.strip()
                try:
                    w, l = int(wins), int(losses)
                    if first_w is None:
                        first_w, first_l = w, l
                        diff = "-"
                    else:
                        d = ((first_w - w) + (l - first_l)) / 2.0
                        diff = f"{d:.1f}"
                except Exception:
                    diff = raw_diff
                info = TEAM_INFO.get(name, {"kr": name, "color": "#64748b"})
                teams.append({
                    "rank": rank, "team": info["kr"], "color": info["color"],
                    "games": games, "win": wins, "loss": losses, "draw": draws,
                    "pct": pct, "gb": diff,
                })
            return teams

        return {"central": parse(tables[0]), "pacific": parse(tables[1])}
    except Exception as e:
        print(f"[ERROR] standings: {e}")
        return {"central": [], "pacific": []}


# ----------------------------------------------------------------------------
# 2) 날짜별 경기 (최근 30일)
# ----------------------------------------------------------------------------
def fetch_games_by_date(date_str):
    url = "https://baseball.yahoo.co.jp/npb/schedule/"
    try:
        res = requests.get(url, params={"date": date_str}, headers=HEADERS, timeout=15)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")
        games = []
        for item in soup.find_all("li", class_="bb-score__item"):
            home_el = item.find(class_=lambda x: x and "bb-score__homeLogo" in x)
            away_el = item.find(class_=lambda x: x and "bb-score__awayLogo" in x)
            sc_l = item.find("span", class_="bb-score__score--left")
            sc_r = item.find("span", class_="bb-score__score--right")
            status_el = item.find(class_=lambda x: x and "bb-score__status" in x)
            link_el = item.find("p", class_="bb-score__link")
            desc_el = item.find("p", class_="bb-score__description")

            sec = item.find_parent("section")
            title_el = sec.find(class_="bb-score__title") if sec else None
            series_raw = title_el.text.strip() if title_el else ""
            series = ""
            if "ファーストステージ" in series_raw:
                series = "🍁 CS 퍼스트 스테이지"
            elif "ファイナルステージ" in series_raw:
                series = "🔥 CS 파이널 스테이지"
            elif "クライマックス" in series_raw or "CS" in series_raw:
                series = "🍁 클라이맥스 시리즈"
            elif "日本シリーズ" in series_raw:
                series = "🏆 SMBC 일본시리즈"

            label_raw = link_el.text.strip() if link_el else ""
            if not label_raw and status_el:
                label_raw = status_el.text.strip()
            state = game_state(label_raw)
            t_m = re.search(r"\b(\d{1,2}:\d{2})\b", item.get_text(" "))
            start = t_m.group(1) if t_m else ""
            status = status_kr(label_raw)
            if state == "pre" and start:
                status = f"{start} 시작" + (" · 선발 예고" if "予告先発" in label_raw else "")
            a_el = item.find("a", class_="bb-score__content") or item.find("a", href=re.compile(r"/npb/game/\d+/"))
            gm = re.search(r"/npb/game/(\d+)/", a_el.get("href", "")) if a_el else None
            games.append({
                "gid": gm.group(1) if gm else "",
                "home": team_kr(home_el.text.strip()) if home_el else "미정",
                "away": team_kr(away_el.text.strip()) if away_el else "미정",
                "score_home": sc_l.text.strip() if sc_l else "",
                "score_away": sc_r.text.strip() if sc_r else "",
                "status": status,
                "state": state,
                "start": start,
                "venue": venue_kr(desc_el.text.strip()) if desc_el else "",
                "venue_jp": desc_el.text.strip() if desc_el else "",
                "series": series,
            })
        return games
    except Exception as e:
        print(f"[ERROR] games {date_str}: {e}")
        return []


WEEK_KR = ["월", "화", "수", "목", "금", "토", "일"]


def fetch_schedule_30days():
    today = now_jst().date()
    days = []
    for offset in range(-SCHEDULE_DAYS_BACK, SCHEDULE_DAYS_FWD + 1):
        d = today + datetime.timedelta(days=offset)
        date_str = d.strftime("%Y-%m-%d")
        games = fetch_games_by_date(date_str)
        days.append({
            "date": date_str,
            "display": f"{d.month}월 {d.day}일 ({WEEK_KR[d.weekday()]})",
            "is_today": offset == 0,
            "games": games,
        })
    return days


# ----------------------------------------------------------------------------
# 3) 포스트시즌
# ----------------------------------------------------------------------------
def fetch_postseason_live():
    url = "https://baseball.yahoo.co.jp/npb/schedule/?kind=postseason"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")
        out = []
        for sec in soup.find_all("section", class_="bb-score"):
            t_el = sec.find(class_="bb-score__title")
            raw = t_el.text.strip() if t_el else ""
            if "セ・ファースト" in raw:
                stage = "🍁 센트럴 CS 퍼스트"
            elif "パ・ファースト" in raw:
                stage = "🍁 퍼시픽 CS 퍼스트"
            elif "セ・ファイナル" in raw:
                stage = "🔥 센트럴 CS 파이널"
            elif "パ・ファイナル" in raw:
                stage = "🔥 퍼시픽 CS 파이널"
            elif "日本シリーズ" in raw:
                stage = "🏆 SMBC 일본시리즈"
            else:
                stage = translate_text_kr(raw) if raw else "🍁 포스트시즌"
            for it in sec.find_all("li", class_="bb-score__item"):
                home_el = it.find(class_=lambda x: x and "homeLogo" in x)
                away_el = it.find(class_=lambda x: x and "awayLogo" in x)
                sc_l = it.find("span", class_="bb-score__score--left")
                sc_r = it.find("span", class_="bb-score__score--right")
                st_el = it.find("p", class_="bb-score__link") or it.find(class_="bb-score__status")
                desc = it.find("p", class_="bb-score__description")
                out.append({
                    "stage": stage,
                    "home": team_kr(home_el.text.strip()) if home_el else "미정",
                    "away": team_kr(away_el.text.strip()) if away_el else "미정",
                    "score_home": sc_l.text.strip() if sc_l else "",
                    "score_away": sc_r.text.strip() if sc_r else "",
                    "status": status_kr(st_el.text.strip()) if st_el else "경기 전",
                    "venue": venue_kr(desc.text.strip()) if desc else "구장 미정",
                })
        return out
    except Exception as e:
        print(f"[ERROR] postseason live: {e}")
        return []


# 2026 포스트시즌 마스터 일정 (고정 데이터)
POSTSEASON_MASTER = [
    {"stage": "CS 퍼스트 스테이지", "league": "센트럴 리그", "game_num": "1차전", "date_display": "10월 10일 (토)", "time": "14:00", "home": "요미우리 자이언츠 (2위)", "away": "요코하마 DeNA (3위)", "venue": "도쿄 돔", "rules": "3전 2선승제 (전 경기 2위 구장)"},
    {"stage": "CS 퍼스트 스테이지", "league": "퍼시픽 리그", "game_num": "1차전", "date_display": "10월 10일 (토)", "time": "14:00", "home": "세이부 라이온즈 (2위)", "away": "니혼햄 파이터즈 (3위)", "venue": "벨루나 돔", "rules": "3전 2선승제 (전 경기 2위 구장)"},
    {"stage": "CS 퍼스트 스테이지", "league": "센트럴 리그", "game_num": "2차전", "date_display": "10월 11일 (일)", "time": "14:00", "home": "요미우리 자이언츠 (2위)", "away": "요코하마 DeNA (3위)", "venue": "도쿄 돔", "rules": "3전 2선승제"},
    {"stage": "CS 퍼스트 스테이지", "league": "퍼시픽 리그", "game_num": "2차전", "date_display": "10월 11일 (일)", "time": "14:00", "home": "세이부 라이온즈 (2위)", "away": "니혼햄 파이터즈 (3위)", "venue": "벨루나 돔", "rules": "3전 2선승제"},
    {"stage": "CS 퍼스트 스테이지", "league": "센트럴 리그", "game_num": "3차전", "date_display": "10월 12일 (월)", "time": "14:00", "home": "요미우리 자이언츠 (2위)", "away": "요코하마 DeNA (3위)", "venue": "도쿄 돔", "rules": "동률 시 2위 진출 (1승 1패 시 진행)"},
    {"stage": "CS 퍼스트 스테이지", "league": "퍼시픽 리그", "game_num": "3차전", "date_display": "10월 12일 (월)", "time": "14:00", "home": "세이부 라이온즈 (2위)", "away": "니혼햄 파이터즈 (3위)", "venue": "벨루나 돔", "rules": "동률 시 2위 진출 (1승 1패 시 진행)"},
    {"stage": "CS 파이널 스테이지", "league": "센트럴 리그", "game_num": "1차전", "date_display": "10월 14일 (수)", "time": "18:00", "home": "한신 타이거스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "한신 고시엔 구장", "rules": "6전 4선승제 (1위팀 1승 어드밴티지)"},
    {"stage": "CS 파이널 스테이지", "league": "퍼시픽 리그", "game_num": "1차전", "date_display": "10월 14일 (수)", "time": "18:00", "home": "소프트뱅크 호크스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "미즈호 PayPay 돔 후쿠오카", "rules": "6전 4선승제 (1위팀 1승 어드밴티지)"},
    {"stage": "CS 파이널 스테이지", "league": "센트럴 리그", "game_num": "2차전", "date_display": "10월 15일 (목)", "time": "18:00", "home": "한신 타이거스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "한신 고시엔 구장", "rules": "전 경기 1위 홈구장 개최"},
    {"stage": "CS 파이널 스테이지", "league": "퍼시픽 리그", "game_num": "2차전", "date_display": "10월 15일 (목)", "time": "18:00", "home": "소프트뱅크 호크스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "미즈호 PayPay 돔 후쿠오카", "rules": "전 경기 1위 홈구장 개최"},
    {"stage": "CS 파이널 스테이지", "league": "센트럴 리그", "game_num": "3차전", "date_display": "10월 16일 (금)", "time": "18:00", "home": "한신 타이거스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "한신 고시엔 구장", "rules": "전 경기 1위 홈구장 개최"},
    {"stage": "CS 파이널 스테이지", "league": "퍼시픽 리그", "game_num": "3차전", "date_display": "10월 16일 (금)", "time": "18:00", "home": "소프트뱅크 호크스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "미즈호 PayPay 돔 후쿠오카", "rules": "전 경기 1위 홈구장 개최"},
    {"stage": "CS 파이널 스테이지", "league": "센트럴 리그", "game_num": "4차전", "date_display": "10월 17일 (토)", "time": "14:00", "home": "한신 타이거스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "한신 고시엔 구장", "rules": "4승 선착 시 조기 종료"},
    {"stage": "CS 파이널 스테이지", "league": "퍼시픽 리그", "game_num": "4차전", "date_display": "10월 17일 (토)", "time": "18:00", "home": "소프트뱅크 호크스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "미즈호 PayPay 돔 후쿠오카", "rules": "4승 선착 시 조기 종료"},
    {"stage": "CS 파이널 스테이지", "league": "센트럴 리그", "game_num": "5차전", "date_display": "10월 18일 (일)", "time": "14:00", "home": "한신 타이거스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "한신 고시엔 구장", "rules": "4승 선착 시 조기 종료"},
    {"stage": "CS 파이널 스테이지", "league": "퍼시픽 리그", "game_num": "5차전", "date_display": "10월 18일 (일)", "time": "14:00", "home": "소프트뱅크 호크스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "미즈호 PayPay 돔 후쿠오카", "rules": "4승 선착 시 조기 종료"},
    {"stage": "CS 파이널 스테이지", "league": "센트럴 리그", "game_num": "6차전", "date_display": "10월 19일 (월)", "time": "18:00", "home": "한신 타이거스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "한신 고시엔 구장", "rules": "최종 6차전 (동률 시 1위 진출)"},
    {"stage": "CS 파이널 스테이지", "league": "퍼시픽 리그", "game_num": "6차전", "date_display": "10월 19일 (월)", "time": "18:00", "home": "소프트뱅크 호크스 (1위)", "away": "CS 퍼스트 스테이지 승자", "venue": "미즈호 PayPay 돔 후쿠오카", "rules": "최종 6차전 (동률 시 1위 진출)"},
    {"stage": "SMBC 일본시리즈", "league": "NPB 통합 챔피언십", "game_num": "1차전", "date_display": "10월 24일 (토)", "time": "18:30", "home": "센트럴 리그 우승팀", "away": "퍼시픽 리그 우승팀", "venue": "센트럴 홈구장", "rules": "7전 4선승제 (1·2차전 센트럴 홈)"},
    {"stage": "SMBC 일본시리즈", "league": "NPB 통합 챔피언십", "game_num": "2차전", "date_display": "10월 25일 (일)", "time": "18:30", "home": "센트럴 리그 우승팀", "away": "퍼시픽 리그 우승팀", "venue": "센트럴 홈구장", "rules": "7전 4선승제"},
    {"stage": "SMBC 일본시리즈", "league": "NPB 통합 챔피언십", "game_num": "3차전", "date_display": "10월 27일 (화)", "time": "18:30", "home": "퍼시픽 리그 우승팀", "away": "센트럴 리그 우승팀", "venue": "퍼시픽 홈구장", "rules": "3·4·5차전 퍼시픽 홈 (10/26 이동일)"},
    {"stage": "SMBC 일본시리즈", "league": "NPB 통합 챔피언십", "game_num": "4차전", "date_display": "10월 28일 (수)", "time": "18:30", "home": "퍼시픽 리그 우승팀", "away": "센트럴 리그 우승팀", "venue": "퍼시픽 홈구장", "rules": "7전 4선승제"},
    {"stage": "SMBC 일본시리즈", "league": "NPB 통합 챔피언십", "game_num": "5차전", "date_display": "10월 29일 (목)", "time": "18:30", "home": "퍼시픽 리그 우승팀", "away": "센트럴 리그 우승팀", "venue": "퍼시픽 홈구장", "rules": "4승 선착 시 조기 종료"},
    {"stage": "SMBC 일본시리즈", "league": "NPB 통합 챔피언십", "game_num": "6차전", "date_display": "10월 31일 (토)", "time": "18:30", "home": "센트럴 리그 우승팀", "away": "퍼시픽 리그 우승팀", "venue": "센트럴 홈구장", "rules": "6·7차전 센트럴 홈 (10/30 이동일)"},
    {"stage": "SMBC 일본시리즈", "league": "NPB 통합 챔피언십", "game_num": "7차전", "date_display": "11월 01일 (일)", "time": "18:30", "home": "센트럴 리그 우승팀", "away": "퍼시픽 리그 우승팀", "venue": "센트럴 홈구장", "rules": "최종 7차전 챔피언 결정전"},
]


# ----------------------------------------------------------------------------
# 4) 규정타석 타자 성적
# ----------------------------------------------------------------------------
TEAM_ABBR = {
    "神": ("한신 타이거스", "#EAB308"), "広": ("히로시마 도요 카프", "#EF4444"),
    "デ": ("요코하마 DeNA 베이스타스", "#2563EB"), "巨": ("요미우리 자이언츠", "#F97316"),
    "ヤ": ("야쿠르트 스왈로스", "#475569"), "中": ("주니치 드래곤즈", "#3B82F6"),
    "ソ": ("소프트뱅크 호크스", "#FBBF24"), "日": ("니혼햄 파이터즈", "#06B6D4"),
    "ロ": ("지바 롯데 마린스", "#94A3B8"), "楽": ("라쿠텐 골든이글스", "#991B1B"),
    "西": ("세이부 라이온즈", "#2563EB"), "オ": ("오릭스 버팔로즈", "#1E293B"),
}


def player_name_kr(name):
    """번역 사전 우선, 없으면 번역기로라도 한국어화."""
    kr = translate_player_name(name)
    if kr == name and JP_RE.search(name):
        kr = translate_text_kr(name)
    return kr


def fetch_batters():
    abbr = TEAM_ABBR
    urls = [
        f"https://npb.jp/bis/{SEASON}/stats/bat_c.html",
        f"https://npb.jp/bis/{SEASON}/stats/bat_p.html",
    ]
    out = []
    for url in urls:
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code != 200:
                continue
            soup = BeautifulSoup(res.content.decode("utf-8", errors="ignore"), "html.parser")
            table = soup.find("table")
            if not table:
                continue
            for r in table.find_all("tr")[1:]:
                cells = [c.text.strip().replace("　", " ")
                         for c in r.find_all(["td", "th"])]
                if len(cells) < 24:
                    continue
                raw = cells[1]
                if "(" in raw and ")" in raw:
                    name, ab = raw.split("(")
                    ab = ab.replace(")", "").strip()
                    name = name.strip()
                else:
                    name, ab = raw.strip(), ""
                team_kr, color = abbr.get(ab, ("기타", "#9ca3af"))

                def f(i):
                    try:
                        return float(cells[i]) if cells[i] not in (".", "") else 0.0
                    except ValueError:
                        return 0.0

                def n(i):
                    try:
                        return int(cells[i])
                    except ValueError:
                        return 0

                out.append({
                    "name": player_name_kr(name),
                    "name_jp": name,
                    "team": team_kr, "color": color,
                    "avg": f(2), "hr": n(10), "sb": n(13),
                    "slg": f(22), "obp": f(23),
                })
        except Exception as e:
            print(f"[ERROR] batters {url}: {e}")
    return out


# ----------------------------------------------------------------------------
# 4-2) 규정투구회 투수 성적
#   npb.jp 표 열: 0순위 1투수 2방어율 3등판 4승 5패 6세이브 7홀드 8HP 9완투 10완봉
#   11무사구 12승률 13타자 14투구회(소수부가 별도 칸일 수 있음) ... 안타 본루타 사구
#   고의사구 사구 삼진 폭투 보크 실점 자책점  → 투구회 이후 열은 끝에서부터 센다.
# ----------------------------------------------------------------------------
def _innings_to_float(whole, frac):
    """'180' + '.1' → 180.333 (일본식 1/3 이닝 표기)."""
    try:
        w = int(re.sub(r"\D", "", whole) or 0)
    except ValueError:
        w = 0
    f = re.sub(r"\D", "", frac or "")
    thirds = int(f[0]) if f else 0
    return w + thirds / 3.0


def fetch_pitchers():
    urls = [
        f"https://npb.jp/bis/{SEASON}/stats/pit_c.html",
        f"https://npb.jp/bis/{SEASON}/stats/pit_p.html",
    ]
    out = []
    for url in urls:
        try:
            res = requests.get(url, headers=HEADERS, timeout=15)
            if res.status_code != 200:
                print(f"[WARN] pitchers {url}: HTTP {res.status_code}")
                continue
            soup = BeautifulSoup(res.content.decode("utf-8", errors="ignore"), "html.parser")
            table = soup.find("table")
            if not table:
                continue
            for r in table.find_all("tr")[1:]:
                cells = [c.text.strip().replace("　", " ")
                         for c in r.find_all(["td", "th"])]
                if len(cells) < 25:
                    continue
                raw = cells[1]
                if "(" in raw and ")" in raw:
                    name, ab = raw.split("(", 1)
                    ab, name = ab.replace(")", "").strip(), name.strip()
                else:
                    name, ab = raw.strip(), ""
                team, color = TEAM_ABBR.get(ab, ("기타", "#9ca3af"))

                def num(v, cast=int):
                    try:
                        return cast(v) if v not in ("", ".", "-") else cast(0)
                    except ValueError:
                        return cast(0)

                # 투구회: 14번 칸부터 (끝-10)번 칸 직전까지 (1칸 또는 2칸)
                ip_cells = cells[14:len(cells) - 10]
                if len(ip_cells) >= 2:
                    ip = _innings_to_float(ip_cells[0], ip_cells[1])
                elif ip_cells:
                    parts = ip_cells[0].split(".")
                    ip = _innings_to_float(parts[0], parts[1] if len(parts) > 1 else "")
                else:
                    ip = 0.0
                hits, walks, hbp = num(cells[-10]), num(cells[-8]), num(cells[-6])
                so, er = num(cells[-5]), num(cells[-1])
                whole = int(ip)
                ip_disp = f"{whole}" + (f" {round((ip - whole) * 3)}/3" if ip - whole > 0.01 else "")

                out.append({
                    "name": player_name_kr(name),
                    "name_jp": name,
                    "team": team, "color": color,
                    "era": num(cells[2], float),
                    "g": num(cells[3]), "w": num(cells[4]), "l": num(cells[5]),
                    "sv": num(cells[6]), "hld": num(cells[7]),
                    "pct": num(cells[12], float),
                    "ip": round(ip, 3), "ip_disp": ip_disp,
                    "so": so, "bb": walks, "hbp": hbp, "h": hits, "er": er,
                    "whip": round((hits + walks) / ip, 2) if ip else 0.0,
                })
        except Exception as e:
            print(f"[ERROR] pitchers {url}: {e}")
    return out


# ----------------------------------------------------------------------------
# 5) 금일 야구 기사 요약
# ----------------------------------------------------------------------------
def detect_category(text):
    if any(k in text for k in ["ドラフト", "スカウト", "指名", "高校生", "大学生", "社会人"]):
        return "🎯 드래프트 & 스카우트"
    if any(k in text for k in ["監督", "コーチ", "就任", "退任", "解任", "退団"]):
        return "👔 감독·코치진"
    if any(k in text for k in ["戦力外", "引退", "FA", "トレード", "契約", "移籍", "去就", "自由契約"]):
        return "📋 전력외·은퇴·이적"
    if any(k in text for k in ["練習", "キャンプ", "調整", "登板", "実戦", "自主トレ"]):
        return "⚾ 선수단 훈련"
    if any(k in text for k in ["インタビュー", "語る", "明かす", "決意", "会見"]):
        return "🎙 인터뷰 & 코멘트"
    if any(k in text for k in ["CS", "クライマックス", "日本シリーズ", "勝", "敗", "完封", "サヨナラ", "本塁打", "突破", "王手"]):
        return "🏆 포스트시즌 & 경기"
    return "📰 구단 소식"


# 기사 속 구단 판별용 키워드 (정식명/애칭/약칭 → 한국어 구단명)
TEAM_DETECT = [
    (["読売", "巨人", "ジャイアンツ"], "巨人"), (["阪神", "タイガース"], "阪神"),
    (["中日", "ドラゴンズ"], "中日"), (["DeNA", "ベイスターズ"], "DeNA"),
    (["ヤクルト", "スワローズ"], "ヤクルト"), (["広島", "カープ"], "広島"),
    (["ソフトバンク", "ホークス"], "ソフトバンク"), (["オリックス", "バファローズ"], "オリックス"),
    (["ロッテ", "マリーンズ"], "ロッテ"), (["楽天", "イーグルス"], "楽天"),
    (["西武", "ライオンズ"], "西武"), (["日本ハム", "ファイターズ", "日ハム"], "日本ハム"),
]

MEDIA_KR = {
    "日刊スポーツ": "닛칸스포츠", "サンスポ": "산케이스포츠", "サンケイスポーツ": "산케이스포츠",
    "スポニチ": "스포츠닛폰", "スポニチアネックス": "스포츠닛폰", "スポーツ報知": "스포츠호치",
    "報知新聞": "호치신문", "デイリースポーツ": "데일리스포츠", "中日スポーツ": "주니치스포츠",
    "東スポ": "도쿄스포츠", "東京スポーツ": "도쿄스포츠", "Full-Count": "풀카운트",
    "Yahoo!ニュース": "야후 뉴스", "NPB": "NPB 공식", "朝日新聞": "아사히신문",
    "毎日新聞": "마이니치신문", "読売新聞": "요미우리신문", "産経ニュース": "산케이뉴스",
    "日本経済新聞": "닛케이신문", "共同通信": "교도통신", "時事通信": "지지통신",
    "NHK": "NHK", "ベースボールキング": "베이스볼 킹", "週刊ベースボール": "주간 베이스볼",
    "THE ANSWER": "THE ANSWER", "Number Web": "Number Web", "西日本スポーツ": "니시닛폰스포츠",
}

CATEGORY_SUMMARY = {
    "🎯 드래프트 & 스카우트": "드래프트 지명 후보와 스카우트 동향을 다룬 기사입니다.",
    "👔 감독·코치진": "감독·코치진 인사와 선임·퇴임 소식을 전하는 기사입니다.",
    "📋 전력외·은퇴·이적": "전력외 통고, 은퇴, FA·트레이드 등 선수단 이동 소식입니다.",
    "⚾ 선수단 훈련": "선수단 훈련 상황과 컨디션 조율 소식을 전하는 기사입니다.",
    "🎙 인터뷰 & 코멘트": "선수·지도자의 인터뷰와 발언을 정리한 기사입니다.",
    "🏆 포스트시즌 & 경기": "경기 결과와 주요 선수 활약, 포스트시즌 판도를 다룬 기사입니다.",
    "📰 구단 소식": "구단 공식 발표와 각종 소식을 전하는 기사입니다.",
}


def detect_team(text):
    for keys, jp in TEAM_DETECT:
        if any(k in text for k in keys):
            info = TEAM_INFO[jp]
            return info["kr"], info["color"]
    return "NPB 종합", "#3b82f6"


def media_kr(name):
    name = (name or "").strip()
    if not name:
        return "스포츠 뉴스"
    if name in MEDIA_KR:
        return MEDIA_KR[name]
    for jp, ko in MEDIA_KR.items():
        if jp in name:
            return ko
    return translate_text_kr(name) if JP_RE.search(name) else name


def fetch_news(limit=30, query="プロ野球 OR NPB when:2d", force_team=None):
    """Google 뉴스(일본) RSS → 한국어 기사 목록. force_team=(한국어팀명, 색) 이면 구단 고정."""
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"
    raw, seen = [], set()
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        items = re.findall(r"<item>(.*?)</item>", res.text, re.DOTALL)
        for it in items:
            t_m = re.search(r"<title>(.*?)</title>", it)
            l_m = re.search(r"<link>(.*?)</link>", it)
            p_m = re.search(r"<pubDate>(.*?)</pubDate>", it)
            if not t_m:
                continue
            raw_t = html.unescape(t_m.group(1))
            media = ""
            if " - " in raw_t:
                clean_t, media = raw_t.rsplit(" - ", 1)
            else:
                clean_t = raw_t
            if clean_t in seen:
                continue
            seen.add(clean_t)

            dt = None
            if p_m:
                try:
                    dt = datetime.datetime.strptime(p_m.group(1)[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                    dt = dt.replace(tzinfo=datetime.timezone.utc).astimezone(JST)
                except Exception:
                    dt = None
            raw.append((dt, clean_t, media, l_m.group(1) if l_m else ""))
    except Exception as e:
        print(f"[ERROR] news: {e}")
        return []

    # 최신순 정렬 후 상위 limit 건만 번역
    raw.sort(key=lambda x: x[0] or datetime.datetime.min.replace(tzinfo=JST), reverse=True)
    today = now_jst().date()
    out = []
    for dt, clean_t, media, link in raw[:limit]:
        if dt is None:
            time_disp = "최근"
        elif dt.date() == today:
            time_disp = f"오늘 {dt:%H:%M}"
        elif dt.date() == today - datetime.timedelta(days=1):
            time_disp = f"어제 {dt:%H:%M}"
        else:
            time_disp = f"{dt.month}/{dt.day} {dt:%H:%M}"

        t_kr, color = force_team or detect_team(clean_t)
        cat = detect_category(clean_t)
        subject = t_kr if t_kr != "NPB 종합" else "일본 프로야구"
        out.append({
            "title": translate_text_kr(clean_t),
            "summary": f"{subject} 관련 — {CATEGORY_SUMMARY.get(cat, '')}",
            "url": link, "time": time_disp, "is_today": bool(dt and dt.date() == today),
            "media": media_kr(media),
            "team": t_kr, "color": color, "category": cat,
        })
    return out


def fetch_team_news(per_team=5):
    """12개 구단별 최신 기사 (마이팀 탭용)."""
    out = {}
    for info in TEAM_INFO.values():
        kr = info["kr"]
        jp_full = TEAM_SEARCH_KEYWORDS.get(kr, kr)
        out[kr] = fetch_news(limit=per_team, query=f"{jp_full} when:3d",
                             force_team=(kr, info["color"]))
        print(f"[OK] {kr} 기사 {len(out[kr])}건")
    return out


# ----------------------------------------------------------------------------
# 실행
# ----------------------------------------------------------------------------
def save(name, obj):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"[OK] {name}  ({os.path.getsize(path):,} bytes)")


def main():
    print(f"=== NPB 수집 시작 ({now_jst():%Y-%m-%d %H:%M} JST, 시즌 {SEASON}) ===")

    save("standings.json", fetch_standings())
    save("schedule.json", {
        "days_back": SCHEDULE_DAYS_BACK,
        "days_fwd": SCHEDULE_DAYS_FWD,
        "days": fetch_schedule_30days(),
    })
    save("postseason.json", {
        "master": POSTSEASON_MASTER,
        "live": fetch_postseason_live(),
    })
    save("batters.json", fetch_batters())
    save("pitchers.json", fetch_pitchers())
    save("news.json", fetch_news())
    save("news_teams.json", fetch_team_news())
    save("meta.json", {
        "updated_at_jst": now_jst().strftime("%Y-%m-%d %H:%M"),
        "updated_at_kst": now_jst().strftime("%Y-%m-%d %H:%M"),  # JST=KST
        "season": SEASON,
    })

    print("=== 수집 완료 ===")


# ----------------------------------------------------------------------------
# 실시간 모드: 오늘 경기 점수만 빠르게 수집 → data/live.json
#   live.yml 워크플로가 경기 시간대에 1~2분 간격으로 반복 호출한다.
#   마지막 줄에 CONTINUE / STOP 을 출력해 반복 여부를 알려준다.
# ----------------------------------------------------------------------------
LIVE_LOOKAHEAD_MIN = 75   # 다음 경기 시작이 이보다 멀면 일단 종료 (다음 예약 실행이 이어받음)


def live_decision(games, now):
    """반복 수집을 계속할지 결정."""
    if not games:
        return "STOP", "오늘 경기 없음"
    if any(g["state"] == "live" for g in games):
        return "CONTINUE", "진행 중 경기 있음"
    pending = [g for g in games if g["state"] == "pre"]
    if not pending:
        return "STOP", "오늘 경기 모두 종료"
    starts = []
    for g in pending:
        try:
            h, m = map(int, g["start"].split(":"))
            starts.append(now.replace(hour=h, minute=m, second=0, microsecond=0))
        except Exception:
            pass
    if starts:
        nxt = min(starts)
        mins = (nxt - now).total_seconds() / 60
        if mins > LIVE_LOOKAHEAD_MIN:
            return "STOP", f"다음 경기까지 {int(mins)}분 남음"
        if mins < -60:
            # 시작 시각이 한참 지났는데 아직 '경기 전' → 지연/중단 가능성, 밤 늦게까지만 대기
            return ("CONTINUE", "개시 지연 대기") if now.hour < 23 else ("STOP", "늦은 시각")
        return "CONTINUE", f"곧 경기 시작 ({int(mins)}분 후)"
    return ("CONTINUE", "시작 시각 미확인") if now.hour < 22 else ("STOP", "늦은 시각")


def run_live():
    now = now_jst()
    today = now.strftime("%Y-%m-%d")
    games = fetch_games_by_date(today)
    ps_live = fetch_postseason_live()
    decision, reason = live_decision(games, now)
    save("live.json", {
        "date": today,
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "any_live": any(g["state"] == "live" for g in games),
        "games": games,
        "postseason": ps_live,
        "note": reason,
    })
    print(f"[LIVE] {len(games)}경기 · {reason}")
    print(decision)


if __name__ == "__main__":
    import sys
    if "--live" in sys.argv:
        run_live()
    else:
        main()
