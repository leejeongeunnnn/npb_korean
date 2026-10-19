# -*- coding: utf-8 -*-
"""
텔레그램 득점 알림.

실시간 수집(collect.py --live)이 돌 때마다 직전 live.json 과 비교해서
  · 경기 시작  · 득점(점수가 바뀔 때, 문자중계의 득점 장면 문장 포함)  · 경기 종료
를 텔레그램 봇으로 보낸다. 이미 보낸 알림은 live.json 의 'notified' 에 기록해 두어 중복 전송을 막는다.

필요한 GitHub 설정 (Settings → Secrets and variables → Actions)
  Secrets   TELEGRAM_BOT_TOKEN : @BotFather 에서 받은 봇 토큰
            TELEGRAM_CHAT_ID   : 알림 받을 대화 ID (telegram_test.yml 실행하면 봇이 알려 줌)
  Variables NOTIFY_TEAMS       : 알림 받을 팀(쉼표로 여러 팀, '*' 는 모든 경기). 없으면 소프트뱅크 호크스
"""
import os
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TEAMS = [t.strip() for t in (os.environ.get("NOTIFY_TEAMS") or "소프트뱅크 호크스").split(",") if t.strip()]


def enabled():
    return bool(TOKEN and CHAT_ID)


def send(text):
    if not enabled():
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                          data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
                                "disable_web_page_preview": "true"}, timeout=15)
        if not r.ok:
            print(f"[TG] 전송 실패 {r.status_code}: {r.text[:120]}")
        return r.ok
    except Exception as e:
        print(f"[TG] 전송 오류: {e}")
        return False


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _short(team):
    return (team or "").split(" ")[0]


def _watched(g):
    return "*" in TEAMS or g.get("home") in TEAMS or g.get("away") in TEAMS


def _score_line(g):
    return f"{_short(g['away'])} {g.get('score_away') or 0} : {g.get('score_home') or 0} {_short(g['home'])}"


def _new_points(detail, sent):
    """문자중계에서 아직 안 보낸 득점 장면들 (오래된 것부터)."""
    out = []
    for inn in (detail or {}).get("innings", []):
        for ev in inn.get("events", []):
            for ln in ev.get("lines", []):
                if ln.get("k") != "point":
                    continue
                key = f"P:{inn['inning']}{inn['half']}:{ev.get('no')}:{ln.get('score', '')}"
                if key in sent:
                    continue
                out.append((key, f"{inn['inning']}회{inn['half']}", ev.get("batter", ""), ln.get("t", ""), ln.get("score", "")))
    return out


def process(prev, new):
    """prev/new: live.json 내용. 보낼 알림을 보내고 new['notified'] 를 채운다."""
    same_day = prev and prev.get("date") == new.get("date")
    notified = dict(prev.get("notified") or {}) if same_day else {}
    prev_games = {g.get("gid"): g for g in (prev.get("games") or [])} if same_day else {}
    details = new.get("details") or {}
    first_time = not same_day      # 그날 첫 실행이면 지난 득점을 한꺼번에 보내지 않도록 현재 상태만 기록

    for g in new.get("games") or []:
        gid = g.get("gid")
        if not gid or not _watched(g):
            continue
        sent = set(notified.get(gid, []))
        p = prev_games.get(gid, {})
        msgs = []
        if g["state"] == "live" and "start" not in sent:
            sent.add("start")
            if not first_time or g.get("score_home") in ("", "0") and g.get("score_away") in ("", "0"):
                msgs.append(f"⚾ <b>경기 시작</b>\n{_esc(_short(g['away']))} @ {_esc(_short(g['home']))} · {_esc(g.get('venue', ''))}")
        score_key = f"S:{g.get('score_away')}-{g.get('score_home')}"
        total = sum(int(x) for x in (g.get("score_home"), g.get("score_away")) if str(x or "").isdigit())
        if g["state"] in ("live", "final") and score_key not in sent and total > 0:
            changed = p and (p.get("score_home"), p.get("score_away")) != (g.get("score_home"), g.get("score_away"))
            points = _new_points(details.get(gid), sent)
            if first_time:
                sent.update(k for k, *_ in points)
            elif changed or points:
                if points:
                    for key, inn, batter, text, sc in points:
                        sent.add(key)
                        msgs.append(f"🔥 <b>득점!</b> {_esc(sc or _score_line(g))}\n{_esc(inn)} · <b>{_esc(batter)}</b>\n{_esc(text)}")
                else:
                    msgs.append(f"🔥 <b>득점!</b> {_esc(_score_line(g))}\n{_esc(g.get('status', ''))}")
            sent.add(score_key)
        if g["state"] == "final" and "end" not in sent:
            sent.add("end")
            if not first_time:
                try:
                    a, h = int(g.get("score_away") or 0), int(g.get("score_home") or 0)
                    res = f"{_short(g['home'])} 승리" if h > a else f"{_short(g['away'])} 승리" if a > h else "무승부"
                except ValueError:
                    res = ""
                msgs.append(f"🏁 <b>경기 종료</b> {_esc(_score_line(g))}\n{_esc(res)}")
        for m in msgs:
            send(m)
        notified[gid] = sorted(sent)
    new["notified"] = notified
    return new
