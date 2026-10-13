# -*- coding: utf-8 -*-
"""화면 점검용: 사이트를 로컬 서버로 띄워 마이팀 하위 탭들을 캡처 (screenshot.yml에서 실행)."""
import sys, json
from playwright.sync_api import sync_playwright

TEAM = sys.argv[1] if len(sys.argv) > 1 else "한신 타이거스"
BASE = "http://localhost:8000/index.html"
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 430, "height": 900}, device_scale_factor=1)
    ctx.add_init_script(f"localStorage.setItem('npb_myteam', {json.dumps(TEAM)});")
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(BASE, wait_until="networkidle"); pg.wait_for_timeout(1500)
    pg.screenshot(path="shots/overview.png", full_page=True)
    for tab in ["schedule", "standings", "players", "stadiums", "news"]:
        pg.click(f'.tab[data-tab="{tab}"]'); pg.wait_for_timeout(3000 if tab == "stadiums" else 1200)
        if tab == "players":
            pg.click('[data-mode="pit"]'); pg.wait_for_timeout(600)
        pg.screenshot(path=f"shots/tab_{tab}.png", full_page=True)
    pg.click('.tab[data-tab="myteam"]'); pg.wait_for_timeout(800)
    for sub in ["profiles", "origin", "travel", "weather"]:
        pg.click(f'[data-sub="{sub}"]')
        pg.wait_for_timeout(4500 if sub in ("origin", "travel", "weather") else 2000)
        pg.screenshot(path=f"shots/{sub}.png", full_page=True)
    # 데스크톱 폭 출신지 지도
    pg.set_viewport_size({"width": 1280, "height": 900})
    pg.click('[data-sub="origin"]'); pg.wait_for_timeout(4000)
    pg.screenshot(path="shots/origin_desktop.png", full_page=False)
    b.close()
open("shots/errors.txt", "w").write("\n".join(errors) or "none")
print("errors:", errors or "none")
