import requests, os
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
os.makedirs("/tmp/pub", exist_ok=True)
for gid in ["2021039487", "2021039481"]:
    r = requests.get(f"https://baseball.yahoo.co.jp/npb/game/{gid}/text", headers=H, timeout=20)
    open(f"/tmp/pub/{gid}_text.html", "w", encoding="utf-8").write(r.text)
    s = BeautifulSoup(r.text, "html.parser")
    for p in s.select("#text_live p.bb-liveText__summary"):
        print(gid, p.get_text("", strip=True))
