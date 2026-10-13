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
