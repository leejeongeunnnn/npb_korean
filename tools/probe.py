import os, requests, sys
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
out = "/tmp/pub"; os.makedirs(out, exist_ok=True)
pages = {
 "today_top": "https://baseball.yahoo.co.jp/npb/game/2021039486/top",
 "today_stats": "https://baseball.yahoo.co.jp/npb/game/2021039486/stats",
 "today_text": "https://baseball.yahoo.co.jp/npb/game/2021039486/text",
 "today_score": "https://baseball.yahoo.co.jp/npb/game/2021039486/score",
 "past_text": "https://baseball.yahoo.co.jp/npb/game/2021051699/text",
 "past_score": "https://baseball.yahoo.co.jp/npb/game/2021051699/score",
 "past_score_idx": "https://baseball.yahoo.co.jp/npb/game/2021051699/score?index=0510100",
}
for k, u in pages.items():
    try:
        r = requests.get(u, headers=H, timeout=20)
        open(f"{out}/{k}.html", "w", encoding="utf-8").write(r.text)
        print(k, r.status_code, r.url, len(r.text))
    except Exception as e:
        print(k, "ERR", e)
