# -*- coding: utf-8 -*-
"""
오늘(·내일) 경기 상세: 예고 선발, 미리보기, 선발 라인업, 문자중계(한국어).

  python collect_today.py            # 매시간 수집 → data/today.json (오늘·내일 경기)
  collect.py --live 가 fetch_detail() 을 불러 실시간으로 live.json 에 넣는다.

출처: Yahoo! 재팬 스포츠나비 경기 페이지 /top(예고 선발·미리보기·스코어보드), /text(문자중계)
"""
import os, re, sys, json, time, datetime

import requests
from bs4 import BeautifulSoup

import collect as C
import collect_profiles as P
import collect_games as G
import live_text as L

DATA = G.DATA
YID_TO_KR = P.YAHOO_ID_TO_KR
MAX_TRANSLATE_PER_RUN = int(os.environ.get("LIVE_TRANSLATE_MAX", "8"))
_tr_used = 0


def get(url):
    r = requests.get(url, headers=C.HEADERS, timeout=20)
    r.encoding = "utf-8"
    return r


def team_of(el, prefix):
    return YID_TO_KR.get(G.team_from_cls(el, prefix), "")


def name_from_text(jp):
    """링크 없이 글 속에만 나오는 이름 → 한국어 (성 사전 · 가타카나 변환)."""
    jp = (jp or "").strip()
    ko = G.localize_names(jp)
    if not L.JP_RE.search(ko):
        return ko
    if P.KANA_ONLY.match(jp.replace(" ", "")):
        return P.kana_to_hangul(jp).replace(" ", "")
    return G.name_ko(jp)


def rich_text(p):
    """<p> 안의 글을 이어 붙이면서 선수 링크는 한국어 이름으로 바꾼다."""
    out = []
    for c in p.children:
        if getattr(c, "name", None) == "a" and "/npb/player/" in c.get("href", ""):
            m = re.search(r"/player/(\d+)/", c["href"])
            out.append(G.name_ko(c.get_text(strip=True), m.group(1) if m else ""))
        elif hasattr(c, "get_text"):
            out.append(c.get_text(strip=True))
        else:
            out.append(str(c).strip())
    return "".join(out)


def translate_line(src_ko_names):
    """규칙으로 바꾼 문장에 일본어가 남으면 번역기로(캐시). 실행당 호출 수를 제한한다."""
    global _tr_used
    ko, score, outs, base = L.ko_line(src_ko_names, C._replace_teams, name_from_text)
    if L.JP_RE.search(ko):
        key = "L1:" + src_ko_names
        if key not in P.TRANS and _tr_used < MAX_TRANSLATE_PER_RUN:
            _tr_used += 1
            body, _, _, _ = L.split_tail(src_ko_names)
            res = C._call_translators(C._replace_teams(body))
            if res:
                P.TRANS[key] = C._tidy(res)
        if key in P.TRANS:
            ko = P.TRANS[key]
    return ko, score, outs, base


# ----------------------------------------------------------------------------
# /top : 예고 선발 · 미리보기 · 스코어보드
# ----------------------------------------------------------------------------
HAND = {"右投": "우투", "左投": "좌투"}


def parse_starters(soup):
    out = {}
    sec = soup.select_one("#strt_pit")
    if not sec:
        return out
    for item in sec.select("section.bb-splits__item"):
        head = item.select_one(".bb-splitsHead")
        team = team_of(head, r"bb-splitsHead--npbTeam") if head else ""
        row = item.select_one(".bb-splitsPitcherStarting tbody tr")
        if not team or not row:
            continue
        tds = row.find_all("td")
        a = row.find("a", href=True)
        pid = re.search(r"/player/(\d+)/", a["href"]).group(1) if a else ""
        stats = {}
        for tr in item.select(".bb-splitsPitcherInfo--stats tbody tr"):
            th = tr.find("th")
            vals = [td.get_text(strip=True) for td in tr.find_all("td")]
            if th and len(vals) >= 4:
                label = th.get_text(strip=True)
                key = {"今季": "season", "CS": "ps", "日本シリーズ": "ps", "交流戦": "il"}.get(label, label)
                stats[key] = {"label": {"今季": "올 시즌", "CS": "CS", "日本シリーズ": "일본시리즈", "交流戦": "교류전"}.get(label, label),
                              "era": vals[0], "g": vals[1], "w": vals[2], "l": vals[3]}
        img = item.select_one("img.bb-splitsPitcherInfo__img")
        out[team] = {
            "team": team, "pid": pid, "name": G.name_ko(a.get_text(strip=True) if a else "", pid),
            "number": tds[0].get_text(strip=True) if tds else "",
            "hand": HAND.get(tds[1].get_text(strip=True), tds[1].get_text(strip=True)) if len(tds) > 1 else "",
            "photo": img["src"] if img and img.get("src", "").startswith("https://") else "",
            "stats": stats, "recent": [],
        }
    return out


def parse_recent_pitching(soup, starters):
    """'最近の成績' 표: 예고 선발 아래에 팀 순서대로 놓여 있다."""
    sec = soup.select_one("#strt_pit")
    if not sec:
        return
    items = sec.select(".bb-splits--stretch .bb-splits__item")
    for team, item in zip(list(starters), items):
        rows = []
        for tr in item.select("tbody tr"):
            c = [x.get_text(strip=True) for x in tr.find_all(["th", "td"])]
            if len(c) >= 7:
                m = re.match(r"(\d+/\d+)\s*vs\.(.+)", c[0])
                rows.append({"date": m.group(1) if m else c[0], "opp": C.team_kr(m.group(2)).split()[0] if m else "",
                             "res": {"勝": "승", "敗": "패"}.get(c[1], c[1] or "-"), "ip": c[2], "np": c[3],
                             "h": c[4], "so": c[5], "r": c[6]})
        starters[team]["recent"] = rows[:4]


def parse_preview(soup):
    p = soup.select_one("#async-preview p.bb-paragraph")
    return p.get_text(" ", strip=True) if p else ""


def preview_ko(text):
    if not text:
        return ""
    key = "PV1:" + text
    if key not in P.TRANS:
        src = G.localize_names(text)
        res = C._call_translators(C._replace_teams(src))
        if res:
            P.TRANS[key] = C._tidy(res)
    return P.TRANS.get(key, "")


# ----------------------------------------------------------------------------
# /text : 문자중계
# ----------------------------------------------------------------------------
POS_KO = {"投": "투수", "捕": "포수", "一": "1루수", "二": "2루수", "三": "3루수", "遊": "유격수",
          "左": "좌익수", "中": "중견수", "右": "우익수", "指": "지명타자"}


def parse_lineup_p(p):
    """'先攻:ヤクルトのスターティングラインアップは1番:<a>岩田</a>(中)、2番:…' → (선공/후공, 팀, 선수들)"""
    txt = p.get_text("", strip=True)
    m = re.match(r"(先攻|後攻):(.+?)のスターティングラインアップ", txt)
    if not m:
        return None
    side = "away" if m.group(1) == "先攻" else "home"
    players = []
    for a in p.select("a[href*='/npb/player/']"):
        nxt, prv = a.find_next_sibling("span"), a.find_previous_sibling("span")
        nt = nxt.get_text(strip=True) if nxt else ""
        pt = prv.get_text(strip=True) if prv else ""
        om = re.search(r"(\d+)番:?$", pt)
        pm = re.match(r"\((.)\)", nt)
        pid = re.search(r"/player/(\d+)/", a["href"]).group(1)
        players.append({"order": int(om.group(1)) if om else len(players) + 1,
                        "name": G.name_ko(a.get_text(strip=True), pid), "pid": pid,
                        "pos": POS_KO.get(pm.group(1), pm.group(1)) if pm else ""})
    return side, C.team_kr(m.group(2)), players


def parse_text(soup):
    out = {"lineups": {}, "starters_text": "", "innings": []}
    root = soup.select_one("#text_live")
    if not root:
        return out
    for sec in root.select("section.bb-liveText"):
        head = sec.select_one(".bb-liveText__head")
        title = sec.select_one(".bb-liveText__inning")
        title = title.get_text(strip=True) if title else ""
        if "試合前" in title:
            for p in sec.select("p.bb-liveText__summary"):
                lu = parse_lineup_p(p)
                if lu:
                    side, team, players = lu
                    out["lineups"][side] = {"team": team, "players": players}
                else:
                    out["starters_text"] = translate_line(rich_text(p))[0]
            continue
        im = re.match(r"(\d+)回(表|裏)", title)
        if not im:
            continue
        inn = {"inning": int(im.group(1)), "half": "초" if im.group(2) == "表" else "말",
               "team": team_of(head, r"bb-liveText__head--npbTeam") if head else "", "events": [], "summary": {}}
        for li in sec.select("li.bb-liveText__item"):
            if li.select_one(".bb-liveText__itemVideoLink") and not li.select_one(".bb-liveText__batter"):
                continue
            num = li.select_one(".bb-liveText__number")
            bat = li.select_one(".bb-liveText__batter")
            ev = {"no": re.sub(r"\D", "", num.get_text()) if num else "", "order": "", "batter": "", "situation": "", "lines": []}
            if bat:
                o = bat.select_one(".bb-liveText__order")
                a = bat.select_one("a.bb-liveText__player")
                st = bat.select_one(".bb-liveText__state")
                ot = o.get_text(strip=True) if o else ""
                ev["order"] = ot.replace("番", "번").replace("代打", "대타").replace("代走", "대주자")
                if a:
                    m = re.search(r"/player/(\d+)/", a.get("href", ""))
                    ev["batter"] = G.name_ko(a.get_text(strip=True), m.group(1) if m else "")
                ev["situation"] = G.situation_kr(st.get_text(strip=True) if st else "")
            for p in li.select("p.bb-liveText__summary"):
                cls = p.get("class", [])
                kind = "point" if "bb-liveText__summary--point" in cls else "change" if "bb-liveText__summary--change" in cls else ""
                ko, score, outs, base = translate_line(rich_text(p))
                # '투수 교체: … 수비 교체: … 수비 위치 변경: …' 처럼 여러 교체가 한 줄이면 나눠서 보여 준다
                parts = [x.strip() for x in re.split(r"\s(?=수비 교체:|수비 위치 변경:|투수 교체:)", ko) if x.strip()]
                for i, part in enumerate(parts):
                    line = {"t": part, "k": kind}
                    if i == len(parts) - 1:
                        tail = L.tail_text(score, outs, base)
                        if tail:
                            line["tail"] = tail
                        if score:
                            line["score"] = f"{score['away']} {score['a']} : {score['b']} {score['home']}"
                    ev["lines"].append(line)
            if ev["lines"] or ev["batter"]:
                inn["events"].append(ev)
        tb = sec.select_one("table.bb-liveTextTable")
        if tb:
            heads = [x.get_text(strip=True) for x in tb.select("th")]
            vals = [x.get_text(strip=True) for x in tb.select("td")]
            m = dict(zip(heads, vals))
            inn["summary"] = {"r": m.get("得点", ""), "h": m.get("ヒット", ""), "bb": m.get("四死球", "")}
        out["innings"].append(inn)
    out["innings"].sort(key=lambda x: (x["inning"], x["half"] == "말"))
    return out


# ----------------------------------------------------------------------------
# 한 경기 상세
# ----------------------------------------------------------------------------
def fetch_detail(gid, game=None, with_text=True):
    game = game or {}
    top = BeautifulSoup(get(f"https://baseball.yahoo.co.jp/npb/game/{gid}/top").text, "html.parser")
    starters = parse_starters(top)
    try:
        parse_recent_pitching(top, starters)
    except Exception as e:
        print(f"[WARN] 최근 성적 {gid}: {e}")
    pv = parse_preview(top)
    d = {"gid": gid, "updated_at": C.now_jst().strftime("%Y-%m-%d %H:%M:%S"),
         "home": game.get("home", ""), "away": game.get("away", ""), "venue": game.get("venue", ""),
         "start": game.get("start", ""), "state": game.get("state", ""),
         "starters": {}, "preview": preview_ko(pv), "preview_ja": pv, "lineups": {}, "innings": [], "linescore": []}
    for team, s in starters.items():
        side = "home" if team == d["home"] else "away" if team == d["away"] else ""
        if side:
            d["starters"][side] = s
    try:
        d["linescore"] = G.parse_top(top).get("linescore", [])
    except Exception:
        pass
    if with_text:
        time.sleep(0.3)
        tx = parse_text(BeautifulSoup(get(f"https://baseball.yahoo.co.jp/npb/game/{gid}/text").text, "html.parser"))
        d["lineups"], d["innings"], d["starters_text"] = tx["lineups"], tx["innings"], tx["starters_text"]
    return d


def todays_games(days=(0, 1)):
    sch = P.load_json(os.path.join(DATA, "schedule.json"), {})
    today = C.now_jst().date()
    want = {(today + datetime.timedelta(days=k)).isoformat(): k for k in days}
    out = []
    for day in sch.get("days", []):
        if day.get("date") in want:
            for g in day.get("games", []):
                if g.get("gid") and g.get("state") != "cancel":
                    out.append((day["date"], want[day["date"]], g))
    return out


def main():
    out = {"updated_at": C.now_jst().strftime("%Y-%m-%d %H:%M"), "games": {}}
    for date, offset, g in todays_games():
        try:
            d = fetch_detail(g["gid"], g, with_text=(offset == 0))
            d["date"] = date
            out["games"][g["gid"]] = d
            n_ev = sum(len(i["events"]) for i in d["innings"])
            print(f"[TODAY] {date} {g['away']} @ {g['home']}: 선발 {len(d['starters'])}명, "
                  f"라인업 {len(d['lineups'])}팀, 문자중계 {n_ev}타석")
        except Exception as e:
            print(f"[WARN] today {g.get('gid')}: {e}")
        time.sleep(0.4)
    P.save_json(os.path.join(DATA, "today.json"), out, compact=True)
    P.save_json(P.TRANS_PATH, P.TRANS, compact=True)


if __name__ == "__main__":
    main()
