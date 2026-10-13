import re, requests
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
r = requests.get("https://baseball.yahoo.co.jp/npb/teams/5/schedule", params={"month": "2026-03"}, headers=H, timeout=20); r.encoding = "utf-8"
s = BeautifulSoup(r.text, "html.parser")
sel = s.select_one(".bb-scheduleNavi__item--selected"); print("SELECTED:", sel.get_text(strip=True) if sel else None)
for td in s.select("td.bb-calendarTable__data"):
    if td.select_one(".bb-calendarTable__date") and td.select_one(".bb-calendarTable__teamName"):
        print("TD", td.get("class"), str(td)[:900].replace("\n", " "))
r = requests.get("https://baseball.yahoo.co.jp/npb/teams/5/schedule", params={"month": "2026-11"}, headers=H, timeout=20); r.encoding = "utf-8"
s = BeautifulSoup(r.text, "html.parser"); sel = s.select_one(".bb-scheduleNavi__item--selected")
print("NOV SELECTED:", sel.get_text(strip=True) if sel else None, "| final url:", r.url)
