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
    # 구장 가는 법: 소프트뱅크 카드 펼치고 지도에서 역 보기
    try:
        pg.click('.tab[data-tab="stadiums"]'); pg.wait_for_timeout(1500)
        pg.evaluate("""() => { const b = document.querySelector('[data-focus="소프트뱅크 호크스"]'); b.closest('details').open = true; }""")
        pg.click('[data-focus="소프트뱅크 호크스"]', timeout=8000); pg.wait_for_timeout(3500)
        pg.screenshot(path="shots/stadium_access_map.png")
        pg.locator('[data-focus="소프트뱅크 호크스"]').scroll_into_view_if_needed(); pg.wait_for_timeout(500)
        pg.screenshot(path="shots/stadium_access_card.png")
    except Exception as e:
        errors.append("stadium access: " + str(e)[:300])
    # 지난 경기 상세 창: 경기 일정에서 종료 경기 카드를 눌러 연다 (긴 화면으로 한 번에 캡처)
    pg.click('.tab[data-tab="schedule"]'); pg.wait_for_timeout(800)
    pg.set_viewport_size({"width": 430, "height": 3000})
    pg.click('.game.clickable >> nth=0'); pg.wait_for_timeout(2500)
    pg.screenshot(path="shots/game_modal.png")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    # 마이팀 최근 경기 줄을 눌러도 열리는지
    pg.click('.tab[data-tab="myteam"]'); pg.wait_for_timeout(800)
    pg.click('tr.clickable >> nth=0'); pg.wait_for_timeout(2500)
    pg.screenshot(path="shots/game_modal_myteam.png")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    pg.set_viewport_size({"width": 430, "height": 900})
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
