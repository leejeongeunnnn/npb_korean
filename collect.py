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


def translate_text_kr(text, use_api=True):
    """팀명·야구용어 치환 후, 남은 일본어는 선택적으로 무료 API로 번역."""
    if not text:
        return ""
    if text in _TRANS_CACHE:
        return _TRANS_CACHE[text]

    clean = text
    for jp, info in TEAM_INFO.items():
        clean = clean.replace(jp, info["kr"])
    for jp, ko in BASEBALL_TERMS.items():
        clean = clean.replace(jp, ko)

    # 아직 일본어(한자/가나)가 남아 있고 API 사용이 허용되면 번역 시도
    has_jp = re.search(r"[぀-ヿ一-鿿]", clean)
    if has_jp and use_api:
        try:
            api = ("https://api.mymemory.translated.net/get?q="
                   + urllib.parse.quote(clean[:200]) + "&langpair=ja|ko")
            res = requests.get(api, timeout=4)
            if res.status_code == 200:
                data = res.json()
                translated = data.get("responseData", {}).get("translatedText", "")
                if translated and not translated.upper().startswith("MYMEMORY WARNING"):
                    clean = html.unescape(translated)
        except Exception:
            pass

    _TRANS_CACHE[text] = clean
    return clean


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

            games.append({
                "home": home_el.text.strip() if home_el else "미정",
                "away": away_el.text.strip() if away_el else "미정",
                "score_home": sc_l.text.strip() if sc_l else "",
                "score_away": sc_r.text.strip() if sc_r else "",
                "status": status_el.text.strip() if status_el else "",
                "label": link_el.text.strip() if link_el else "",
                "venue": desc_el.text.strip() if desc_el else "",
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
                stage = raw or "🍁 포스트시즌"
            for it in sec.find_all("li", class_="bb-score__item"):
                home_el = it.find(class_=lambda x: x and "homeLogo" in x)
                away_el = it.find(class_=lambda x: x and "awayLogo" in x)
                sc_l = it.find("span", class_="bb-score__score--left")
                sc_r = it.find("span", class_="bb-score__score--right")
                st_el = it.find("p", class_="bb-score__link") or it.find(class_="bb-score__status")
                desc = it.find("p", class_="bb-score__description")
                out.append({
                    "stage": stage,
                    "home": home_el.text.strip() if home_el else "미정",
                    "away": away_el.text.strip() if away_el else "미정",
                    "score_home": sc_l.text.strip() if sc_l else "",
                    "score_away": sc_r.text.strip() if sc_r else "",
                    "status": st_el.text.strip() if st_el else "경기 전",
                    "venue": desc.text.strip() if desc else "구장 미정",
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
def fetch_batters():
    abbr = {
        "神": ("한신 타이거스", "#EAB308"), "広": ("히로시마 도요 카프", "#EF4444"),
        "デ": ("요코하마 DeNA 베이스타스", "#2563EB"), "巨": ("요미우리 자이언츠", "#F97316"),
        "ヤ": ("야쿠르트 스왈로스", "#475569"), "中": ("주니치 드래곤즈", "#3B82F6"),
        "ソ": ("소프트뱅크 호크스", "#FBBF24"), "日": ("니혼햄 파이터즈", "#06B6D4"),
        "ロ": ("지바 롯데 마린스", "#94A3B8"), "楽": ("라쿠텐 골든이글스", "#991B1B"),
        "西": ("세이부 라이온즈", "#2563EB"), "オ": ("오릭스 버팔로즈", "#1E293B"),
    }
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
                    "name": translate_player_name(name),
                    "name_jp": name,
                    "team": team_kr, "color": color,
                    "avg": f(2), "hr": n(10), "sb": n(13),
                    "slg": f(22), "obp": f(23),
                })
        except Exception as e:
            print(f"[ERROR] batters {url}: {e}")
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


def detect_team(text):
    for jp, info in TEAM_INFO.items():
        if jp in text or info["kr"] in text:
            return info["kr"], info["color"]
    return "NPB 종합", "#3b82f6"


def fetch_news(limit=30):
    q = urllib.parse.quote("プロ野球 OR NPB when:2d")
    url = f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"
    out, seen = [], set()
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
            link = l_m.group(1) if l_m else ""
            pub = p_m.group(1) if p_m else ""

            media = "스포츠 뉴스"
            if " - " in raw_t:
                clean_t, media = raw_t.rsplit(" - ", 1)
            else:
                clean_t = raw_t
            if clean_t in seen:
                continue
            seen.add(clean_t)

            time_disp = "최근"
            if pub:
                try:
                    dt = datetime.datetime.strptime(pub[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                    dt = dt + datetime.timedelta(hours=9)
                    time_disp = dt.strftime("%m/%d %H:%M")
                except Exception:
                    pass

            team_kr, color = detect_team(clean_t)
            out.append({
                "title": translate_text_kr(clean_t),
                "title_jp": clean_t,
                "url": link, "time": time_disp, "media": media,
                "team": team_kr, "color": color,
                "category": detect_category(clean_t),
            })
            if len(out) >= limit:
                break
    except Exception as e:
        print(f"[ERROR] news: {e}")
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
    save("news.json", fetch_news())
    save("meta.json", {
        "updated_at_jst": now_jst().strftime("%Y-%m-%d %H:%M"),
        "updated_at_kst": now_jst().strftime("%Y-%m-%d %H:%M"),  # JST=KST
        "season": SEASON,
    })

    print("=== 수집 완료 ===")


if __name__ == "__main__":
    main()
