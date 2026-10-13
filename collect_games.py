# -*- coding: utf-8 -*-
"""
지난 경기 상세 수집 → data/games/<경기ID>.json  (종료된 경기는 한 번만 수집)

  python collect_games.py --minutes 25 --max 400     # 최신 경기부터, 시간/개수 제한 안에서

내용: 이닝별 점수, 승·패·세이브 투수, 홈런, 득점 장면(한국어 번역), 양팀 라인업(타순·포지션·타석 결과),
      양팀 투수 기록. 선수 이름은 Yahoo 선수 ID로 프로필(data/profiles)과 맞춰 한국어로 표기.
"""
import os, re, sys, json, time, glob

import requests
from bs4 import BeautifulSoup

import collect as C
import collect_profiles as P     # 번역 캐시·가나 변환·구단 표 재사용

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
GAMES_DIR = os.path.join(DATA, "games")
YID_TO_KR = P.YAHOO_ID_TO_KR

# ----------------------------------------------------------------------------
# 이름: Yahoo 선수 ID → 한국어 (프로필) / 없으면 번역 사전 · 가나 변환
# ----------------------------------------------------------------------------
NAME_BY_ID = {}
SURNAME_MAP = {}       # 일본어 성 → 한국어 성 (득점 장면 문장 번역 전 치환용)
for path in glob.glob(os.path.join(DATA, "profiles", "*.json")):
    if path.endswith("index.json"):
        continue
    d = P.load_json(path, {})
    for p in d.get("players", []):
        NAME_BY_ID[p["id"]] = p["name"]
        jp_parts, ko_parts = p["name_jp"].split(), p["name"].split()
        if len(jp_parts) >= 2 and len(ko_parts) >= 2 and len(jp_parts[0]) >= 2:
            SURNAME_MAP.setdefault(jp_parts[0], ko_parts[0])


def pid_of(el):
    a = el.find("a", href=True) if el else None
    m = re.search(r"/npb/player/(\d+)/", a["href"]) if a else None
    return m.group(1) if m else ""


def name_ko(jp, pid=""):
    if pid and pid in NAME_BY_ID:
        return NAME_BY_ID[pid]
    clean = re.sub(r"[\s　]", "", jp or "")
    hit = C.PLAYER_NAME_TRANSLATION.get(clean)
    if hit:
        return P.clean_name(re.sub(r"[（(].*?[)）]", "", hit))
    if P.KANA_ONLY.match((jp or "").replace(" ", "")):
        return P.kana_to_hangul(jp)
    return jp            # 한자 이름은 번역기보다 원문이 낫다 (다음 프로필 갱신 때 ID로 채워짐)


# ----------------------------------------------------------------------------
# 야구 용어: 포지션 · 타석 결과
# ----------------------------------------------------------------------------
POS = {"投": "투수", "捕": "포수", "一": "1루수", "二": "2루수", "三": "3루수", "遊": "유격수",
       "左": "좌익수", "中": "중견수", "右": "우익수", "指": "지명타자", "打": "대타", "走": "대주자"}
POS_SHORT = {"投": "투", "捕": "포", "一": "1루", "二": "2루", "三": "3루", "遊": "유격", "左": "좌익",
             "中": "중견", "右": "우익", "指": "지명", "打": "대타", "走": "대주자"}


def pos_kr(s):
    """'(左一)' → '좌익→1루' / '走右' → '대주자→우익'"""
    core = s.strip("()（） ")
    return "→".join(POS_SHORT.get(ch, ch) for ch in core)


FIELD = {"投": "투수", "捕": "포수", "一": "1루수", "二": "2루수", "三": "3루수", "遊": "유격수",
         "左": "좌익수", "中": "중견수", "右": "우익수"}
FIELD_DIR = {"左": "좌", "中": "중", "右": "우", "遊": "유", "二": "2루", "一": "1루", "三": "3루", "投": "투", "捕": "포"}
XB = {"左": "좌익", "中": "중견", "右": "우익", "遊": "유격수 쪽", "二": "2루수 쪽", "一": "1루선상", "三": "3루선상", "投": "투수 쪽", "捕": "포수 쪽"}
WHOLE = {
    "空三振": "헛스윙 삼진", "見三振": "루킹 삼진", "三振": "삼진", "四球": "볼넷", "死球": "몸에 맞는 공",
    "敬遠": "고의4구", "打撃妨": "타격방해", "走塁妨": "주루방해", "野選": "야수선택", "振逃": "낫아웃 출루",
}


def atbat_kr(s):
    """타석 결과 약어 → 한국어. 예) 中飛→중견수 플라이, 左安→좌전 안타, 右２→우익 2루타, 遊併打→유격수 병살타"""
    s = (s or "").strip().replace("２", "2").replace("３", "3")
    if not s:
        return ""
    if s in WHOLE:
        return WHOLE[s]
    f, rest = s[0], s[1:]
    if f not in FIELD:
        return s
    who, d = FIELD[f], FIELD_DIR[f]
    table = [
        ("犠打", f"{who} 희생번트"), ("犠飛", f"{who} 희생플라이"), ("併打", f"{who} 병살타"), ("併殺", f"{who} 병살타"),
        ("邪飛", f"{who} 파울플라이"), ("飛", f"{who} 플라이"), ("ゴロ", f"{who} 땅볼"), ("ゴ", f"{who} 땅볼"), ("直", f"{who} 직선타"),
        ("安", f"{d}전 안타"), ("2", f"{XB.get(f, d)} 2루타"), ("3", f"{XB.get(f, d)} 3루타"), ("本", f"{d}월 홈런"),
        ("失", f"{who} 실책"), ("野選", f"{who} 야수선택"), ("犠失", f"{who} 희생번트 실책"),
    ]
    for k, v in table:
        if rest == k:
            return v
    for k, v in table:                      # '左本' 이외에 '左中本' 같은 변형
        if rest.endswith(k):
            return v
    return s


STATE = {"勝": "승", "敗": "패", "H": "홀드", "Ｈ": "홀드", "S": "세이브", "Ｓ": "세이브"}


# ----------------------------------------------------------------------------
# 득점 장면 문장
# ----------------------------------------------------------------------------
SCORE_RE = re.compile(r"\s([^\s\d]{1,2})\s(\d+)-(\d+)\s([^\s\d]{1,2})(?:\s|$)")
INNING_RE = re.compile(r"(\d+)回(表|裏)")
OUTS = {"無死": "무사", "一死": "1사", "二死": "2사"}
BASES = {"満塁": "만루", "一二塁": "1·2루", "一三塁": "1·3루", "二三塁": "2·3루", "一塁": "1루", "二塁": "2루", "三塁": "3루", "走者なし": "주자 없음"}


def situation_kr(s):
    s = (s or "").strip()
    out = ""
    for k, v in OUTS.items():
        if s.startswith(k):
            out, s = v, s[len(k):]
            break
    return (out + " " + BASES.get(s, s)).strip()


def abbr_kr(a):
    return P.C.TEAM_INFO.get({"楽": "楽天", "ソ": "ソフトバンク", "神": "阪神", "巨": "巨人", "ヤ": "ヤクルト", "中": "中日",
                              "広": "広島", "デ": "DeNA", "日": "日本ハム", "ロ": "ロッテ", "西": "西武", "オ": "オリックス"}.get(a, ""), {}).get("kr", a)


def split_play(text):
    """'…タイムリーツーベース！ 楽 3-1 ソ 二塁 0:56 【5回裏】…' → (설명, 점수표기, 이후 주자)"""
    m = SCORE_RE.search(" " + text + " ")
    if not m:
        return text.strip(), "", ""
    desc = (" " + text)[:m.start()].strip()
    a1, s1, s2, a2 = m.groups()
    score = f"{abbr_kr(a1).split()[0]} {s1}-{s2} {abbr_kr(a2).split()[0]}"
    after = re.sub(r"^\dアウト", "", (" " + text + " ")[m.end():].split(" ")[0])
    return desc, score, BASES.get(after, "")


PLAY_TERMS = [   # 긴 표현부터 치환 (번역기가 모르는 야구 용어를 먼저 한국어로)
    ("先制ホームラン", "선제 홈런"), ("逆転ホームラン", "역전 홈런"), ("同点ホームラン", "동점 홈런"), ("サヨナラホームラン", "끝내기 홈런"),
    ("勝ち越しホームラン", "앞서가는 홈런"), ("逆転タイムリー", "역전 적시타"), ("サヨナラタイムリー", "끝내기 적시타"),
    ("押し出しのフォアボール", "밀어내기 볼넷"), ("押し出しのデッドボール", "밀어내기 몸에 맞는 공"), ("押し出し", "밀어내기"),
    ("満塁ホームラン", "만루 홈런"), ("スリーランホームラン", "3점 홈런"), ("ツーランホームラン", "2점 홈런"),
    ("ソロホームラン", "솔로 홈런"), ("ホームラン", "홈런"),
    ("タイムリースリーベース", "적시 3루타"), ("タイムリーツーベース", "적시 2루타"), ("タイムリー内野安打", "적시 내야안타"),
    ("タイムリーヒット", "적시타"), ("タイムリーエラー", "적시 실책"), ("タイムリー", "적시"),
    ("内野安打", "내야안타"), ("スリーベース", "3루타"), ("ツーベース", "2루타"), ("ヒット", "안타"),
    ("犠牲フライ", "희생플라이"), ("犠牲バント", "희생번트"), ("スクイズ", "스퀴즈 번트"),
    ("セカンドゴロ", "2루수 땅볼"), ("ショートゴロ", "유격수 땅볼"), ("サードゴロ", "3루수 땅볼"),
    ("ファーストゴロ", "1루수 땅볼"), ("ピッチャーゴロ", "투수 땅볼"), ("キャッチャーゴロ", "포수 땅볼"),
    ("内野ゴロ", "내야 땅볼"), ("ゴロ", "땅볼"), ("併殺打", "병살타"), ("ダブルプレー", "병살"), ("併殺", "병살"),
    ("センターフライ", "중견수 플라이"), ("レフトフライ", "좌익수 플라이"), ("ライトフライ", "우익수 플라이"),
    ("フォアボール", "볼넷"), ("デッドボール", "몸에 맞는 공"), ("ワイルドピッチ", "폭투"), ("暴投", "폭투"),
    ("パスボール", "포일"), ("捕逸", "포일"), ("フィルダースチョイス", "야수선택"), ("野選", "야수선택"),
    ("タイムリーエラー", "적시 실책"), ("エラー", "실책"), ("失策", "실책"), ("ボーク", "보크"), ("本盗", "홈스틸"), ("盗塁", "도루"),
    ("先制ホームラン", "선제 홈런"), ("逆転ホームラン", "역전 홈런"), ("同点ホームラン", "동점 홈런"), ("サヨナラホームラン", "끝내기 홈런"),
    ("先制", "선제"), ("勝ち越し", "앞서가는"), ("逆転", "역전"), ("同点", "동점"), ("サヨナラ", "끝내기"), ("追加点", "추가점"),
    ("左中間", "좌중간"), ("右中間", "우중간"),
    ("レフトスタンド", "좌측 관중석"), ("ライトスタンド", "우측 관중석"), ("センタースタンド", "가운데 관중석"), ("バックスクリーン", "백스크린"),
    ("レフトへの", "좌익수 쪽 "), ("センターへの", "중견수 쪽 "), ("ライトへの", "우익수 쪽 "),
    ("レフトへ", "좌익수 쪽으로 "), ("センターへ", "중견수 쪽으로 "), ("ライトへ", "우익수 쪽으로 "),
    ("レフト", "좌익수"), ("センター", "중견수"), ("ライト", "우익수"),
    ("ランナーフルベース", "만루"), ("三塁ランナー", "3루 주자"), ("二塁ランナー", "2루 주자"), ("一塁ランナー", "1루 주자"),
    ("が本塁生還", " 홈인"), ("本塁生還", "홈인"), ("の間に", " 사이에 "), ("を放つ", ""), ("放つ", ""),
    ("0アウト", "무사 "), ("1アウト", "1사 "), ("2アウト", "2사 "), ("満塁", "만루"),
    ("一二塁", "1·2루"), ("一三塁", "1·3루"), ("二三塁", "2·3루"),
    ("(投)", "(투수)"), ("（投）", "(투수)"), ("代打", "대타"), ("代走", "대주자"),
]


def play_ko(text):
    """득점 장면 문장의 야구 용어를 한국어로 바꾸고, 남은 조사·어미를 정리."""
    t = localize_names(text or "")
    t = re.sub(r"(\d)-(\d)から", r"볼카운트 \1-\2에서 ", t)
    for ja, ko in PLAY_TERMS:
        t = t.replace(ja, ko)
    t = t.replace("から", "에서 ").replace("の", " ").replace("を", " ").replace("が", " ").replace("で", " ")
    t = t.replace("！", "!").replace("→", " → ")
    return re.sub(r"\s{2,}", " ", t).strip()


def localize_names(text):
    for jp, ko in sorted(SURNAME_MAP.items(), key=lambda x: -len(x[0])):
        if jp in text:
            text = text.replace(jp, ko)
    return text


# ----------------------------------------------------------------------------
# 경기 파싱
# ----------------------------------------------------------------------------
def get(url):
    time.sleep(P.SLEEP)
    r = requests.get(url, headers=C.HEADERS, timeout=20)
    r.encoding = "utf-8"
    return r


def team_from_cls(el, prefix):
    for c in el.get("class", []):
        m = re.match(prefix + r"(\d+)$", c)
        if m:
            return m.group(1)
    return ""


def parse_top(soup):
    out = {"linescore": [], "decisions": [], "homeruns": [], "plays": []}
    t = soup.select_one("table.bb-gameScoreTable")
    if t:
        rows = t.find_all("tr")
        head = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])][1:]
        for r in rows[1:]:
            cells = [c.get_text(strip=True) for c in r.find_all(["th", "td"])]
            if not cells:
                continue
            a = r.find("a", href=True)
            m = re.search(r"/npb/teams/(\d+)/", a["href"]) if a else None
            team = YID_TO_KR.get(m.group(1)) if m else C.team_kr(cells[0])
            vals = cells[1:]
            n_inn = len(head) - 3
            out["linescore"].append({"team": team, "innings": vals[:n_inn],
                                     "r": vals[n_inn] if len(vals) > n_inn else "",
                                     "h": vals[n_inn + 1] if len(vals) > n_inn + 1 else "",
                                     "e": vals[n_inn + 2] if len(vals) > n_inn + 2 else ""})
        out["innings"] = head[:-3]
    sec = soup.select_one("#pit_rec")
    if sec:
        for tr in sec.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if not th or not td:
                continue
            kind = {"勝利投手": "승리", "敗戦投手": "패전", "セーブ": "세이브"}.get(th.get_text(strip=True), th.get_text(strip=True))
            a = td.select_one("a.bb-gameTable__player")
            rec = re.search(r"\((\d+)勝(\d+)敗(\d+)S\)", td.get_text(" ", strip=True))
            out["decisions"].append({"kind": kind, "team": YID_TO_KR.get(team_from_cls(td, r"bb-gameTable__data--npbTeam"), ""),
                                     "name": name_ko(a.get_text(strip=True) if a else "", pid_of(td)),
                                     "record": f"{rec.group(1)}승 {rec.group(2)}패 {rec.group(3)}세이브" if rec else ""})
    sec = soup.select_one("#homerun")
    if sec:
        for tr in sec.find_all("tr"):
            td = tr.find("td")
            if not td:
                continue
            team = YID_TO_KR.get(team_from_cls(td, r"bb-gameTable__data--npbTeam"), "")
            for a in td.select("a[href*='/npb/player/']"):
                # 'a 이름' 뒤에 '15号（2ラン 투수）' 형태의 글이 이어짐
                tail = ""
                for sib in a.next_siblings:
                    if getattr(sib, "name", None) == "a":
                        break
                    tail += sib.get_text(" ", strip=True) if hasattr(sib, "get_text") else str(sib)
                no = re.search(r"(\d+)号", tail)
                kind = re.search(r"(ソロ|2ラン|3ラン|満塁|２ラン|３ラン)", tail)
                kind_ko = {"ソロ": "솔로", "2ラン": "2점", "２ラン": "2점", "3ラン": "3점", "３ラン": "3점", "満塁": "만루"}.get(kind.group(1), "") if kind else ""
                inn = re.search(r"(\d+)回", tail)
                hm = re.search(r"/player/(\d+)/", a["href"])
                out["homeruns"].append({"team": team, "name": name_ko(a.get_text(strip=True), hm.group(1) if hm else ""),
                                        "no": no.group(1) if no else "", "kind": kind_ko, "inning": inn.group(1) if inn else ""})
    sec = soup.select_one("#scor_ply")
    if sec:
        for tr in sec.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if not th or not td:
                continue
            im = INNING_RE.search(th.get_text(strip=True))
            batter = td.select_one(".bb-gameTable__batter")
            summ = td.select_one(".bb-gameTable__summary")
            order = (td.select_one(".bb-gameTable__order") or BeautifulSoup("", "html.parser")).get_text(strip=True)
            state_el = batter.select_one(".bb-gameTable__state") if batter else None
            pa = td.select_one("a.bb-gameTable__player")
            raw = summ.get_text(" ", strip=True) if summ else ""
            desc, score, after = split_play(raw)
            out["plays"].append({
                "inning": int(im.group(1)) if im else 0, "half": ("초" if im and im.group(2) == "表" else "말") if im else "",
                "team": YID_TO_KR.get(team_from_cls(td, r"bb-gameTable__data--npbTeam"), ""),
                "order": order.replace("番", "번"),
                "batter": name_ko(pa.get_text(strip=True) if pa else "", pid_of(batter) if batter else ""),
                "situation": situation_kr(state_el.get_text(strip=True) if state_el else ""),
                "desc_ja": desc, "desc": "", "score": score, "after": after,
            })
    return out


def parse_stats(soup):
    lineups, pitching = {}, {}
    for t in soup.select("table.bb-statsTable"):
        team = YID_TO_KR.get(team_from_cls(t, r"bb-statsTable--npbTeam"), "")
        rows = t.find_all("tr")
        if not rows:
            continue
        head = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
        inn_cols = [(i, h) for i, h in enumerate(head) if re.match(r"^\d+回$", h)]
        players, order = [], 0
        for r in rows[1:]:
            tds = r.find_all("td")
            cells = [c.get_text(" ", strip=True) for c in tds]
            if len(cells) < 14 or cells[0] in ("合計", "計"):
                continue
            starter = cells[0].startswith("(") or cells[0].startswith("（")
            if starter:
                order += 1
            ab = []
            for i, h in inn_cols:
                v = cells[i] if i < len(cells) else ""
                for part in [x for x in re.split(r"\s+|/", v) if x]:
                    ab.append({"inn": int(h[:-1]), "ja": part, "ko": atbat_kr(part)})
            players.append({
                "order": order, "starter": starter, "pos": pos_kr(cells[0]),
                "name": name_ko(cells[1], pid_of(tds[1])), "avg": cells[2],
                "ab": cells[3], "r": cells[4], "h": cells[5], "rbi": cells[6], "so": cells[7],
                "bb": cells[8], "hbp": cells[9], "sh": cells[10], "sb": cells[11], "e": cells[12], "hr": cells[13],
                "atbats": ab,
            })
        if team:
            lineups[team] = players
    for t in soup.select("table.bb-scoreTable"):
        team = YID_TO_KR.get(team_from_cls(t, r"bb-scoreTable--npbTeam"), "")
        ps = []
        for r in t.find_all("tr")[1:]:
            tds = r.find_all("td")
            c = [x.get_text(" ", strip=True) for x in tds]
            if len(c) < 14:
                continue
            ps.append({"state": STATE.get(c[0], ""), "name": name_ko(c[1], pid_of(tds[1])), "era": c[2],
                       "ip": c[3], "np": c[4], "bf": c[5], "h": c[6], "hr": c[7], "so": c[8], "bb": c[9],
                       "hbp": c[10], "r": c[12], "er": c[13]})
        if team:
            pitching[team] = ps
    return lineups, pitching


def fetch_game(gid, meta):
    top = BeautifulSoup(get(f"https://baseball.yahoo.co.jp/npb/game/{gid}/top").text, "html.parser")
    g = parse_top(top)
    if not g["linescore"]:
        return None
    st = BeautifulSoup(get(f"https://baseball.yahoo.co.jp/npb/game/{gid}/stats").text, "html.parser")
    g["lineups"], g["pitching"] = parse_stats(st)
    g.update({"gid": gid, **meta, "collected_at": C.now_jst().strftime("%Y-%m-%d %H:%M")})
    return g


def translate_plays(games):
    """득점 장면: 야구 용어 사전으로 먼저 한국어화하고, 일본어가 남은 문장만 번역기로."""
    todo = {}
    for g in games:
        for pl in g["plays"]:
            pre = play_ko(pl["desc_ja"])
            if not C.JP_RE.search(pre):
                pl["desc"] = pre
            elif "P2:" + pre in P.TRANS:
                pl["desc"] = P.TRANS["P2:" + pre]
            else:
                todo.setdefault(pre, []).append(pl)
    if todo:
        got = C.translate_batch_kr(list(todo))
        for pre, plays in todo.items():
            ko = got.get(pre)
            if ko:
                P.TRANS["P2:" + pre] = ko
            for pl in plays:
                pl["desc"] = ko or pre
        print(f"[TR] 득점 장면 {len(todo)}개 번역기 사용 ({len(got)}개 성공)")


# ----------------------------------------------------------------------------
# 대상 경기 목록
# ----------------------------------------------------------------------------
def target_games():
    seen, out = set(), []
    S = P.load_json(os.path.join(DATA, "season.json"), {})
    for team, games in S.get("teams", {}).items():
        for g in games:
            if g.get("state") != "final" or not g.get("gid") or g.get("kind") == "exhibition":
                continue
            if g["gid"] in seen:
                continue
            seen.add(g["gid"])
            home, away = (team, g["opp"]) if g["home"] else (g["opp"], team)
            v = S.get("venues", {}).get(g["venue"], {})
            out.append((g["date"], g["gid"], {"date": g["date"], "home": home, "away": away,
                                             "venue": v.get("ko") or g["venue"], "kind": g.get("kind", "regular")}))
    sch = P.load_json(os.path.join(DATA, "schedule.json"), {})
    for d in sch.get("days", []):
        for g in d.get("games", []):
            if g.get("gid") and g.get("state") == "final" and g["gid"] not in seen:
                seen.add(g["gid"])
                out.append((d["date"], g["gid"], {"date": d["date"], "home": g["home"], "away": g["away"],
                                                  "venue": g.get("venue", ""), "kind": "regular"}))
    out.sort(key=lambda x: x[0], reverse=True)         # 최신 경기부터
    return out


def main():
    args = sys.argv[1:]
    minutes = float(args[args.index("--minutes") + 1]) if "--minutes" in args else 20
    max_n = int(args[args.index("--max") + 1]) if "--max" in args else 300
    deadline = time.time() + minutes * 60
    os.makedirs(GAMES_DIR, exist_ok=True)
    todo = [t for t in target_games() if not os.path.exists(os.path.join(GAMES_DIR, f"{t[1]}.json"))]
    print(f"=== 경기 상세 수집: 대상 {len(todo)}경기 (이번 실행 최대 {max_n}경기 / {minutes:.0f}분) ===")
    done, batch = 0, []

    def flush():
        translate_plays(batch)
        for g in batch:
            P.save_json(os.path.join(GAMES_DIR, f"{g['gid']}.json"), g, compact=True)
        batch.clear()
        P.save_json(P.TRANS_PATH, P.TRANS, compact=True)

    for date, gid, meta in todo:
        if done >= max_n or time.time() > deadline:
            print("[STOP] 이번 실행 한도 도달 → 나머지는 다음 실행에서")
            break
        try:
            g = fetch_game(gid, meta)
            if g:
                batch.append(g); done += 1
        except Exception as e:
            print(f"[WARN] game {gid}: {e}")
        if len(batch) >= 20:
            flush()
    flush()
    print(f"=== 완료: {done}경기 저장 ===")


if __name__ == "__main__":
    main()
