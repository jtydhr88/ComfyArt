"""#638 #78 AFTER tip-pin — zh-light live dist Soft mount screenshots (mock $0).

Run: DESIGN_638_78_SHOOT=1 PYTHONPATH=tests:. pytest -q tests/test_design_638_78_shots.py -s
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parents[1] / "left-ours"
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT.parent))
os.chdir(ROOT)

SHOTS = [
    "AFTER-home-quickstart-order-zh-light.png",
    "AFTER-home-chip-website-zh-light.png",
    "AFTER-skills-explore-phase2-b-order-zh-light.png",
    "AFTER-skills-explore-website-chip-zh-light.png",
    "AFTER-skill-modal-commerce-strategist-zh-light.png",
    "AFTER-skill-modal-social-ugc-zh-light.png",
]


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
        pg = await ctx.new_page()
        await pg.add_init_script(
            "localStorage.setItem('comfyart.lang','zh');"
            "localStorage.setItem('comfyart.theme','light');"
            "localStorage.setItem('comfyart.rail.collapsed','0');"
        )
        await pg.goto(app_url)
        await pg.get_by_test_id("home-start-skill").wait_for()
        await pg.get_by_test_id("home-skill-card").first.wait_for()
        await pg.wait_for_timeout(800)

        # 1) Home quick-start first 6 (Phase1 hot — Soft mount does not displace)
        qs = pg.get_by_test_id("home-start-skill")
        await qs.scroll_into_view_if_needed()
        await pg.wait_for_timeout(300)
        await qs.screenshot(path=str(OUT / SHOTS[0]))
        print("wrote", OUT / SHOTS[0])

        # 2) website chip lit
        await pg.get_by_test_id("home-chip-website").click()
        await pg.wait_for_timeout(400)
        box = await pg.get_by_test_id("home-chips").bounding_box()
        grid = await pg.get_by_test_id("home-skill-grid").bounding_box()
        y0 = max(0, (box or {"y": 0})["y"] - 8)
        y1 = ((grid or {"y": 400, "height": 200})["y"] + (grid or {"height": 200})["height"] + 24)
        await pg.screenshot(
            path=str(OUT / SHOTS[1]),
            clip={"x": 0, "y": y0, "width": 1280, "height": min(800, y1 - y0)},
        )
        print("wrote", OUT / SHOTS[1])

        # 3) Skills Explore — forYou wall with Phase2 B after Phase1
        await pg.goto(app_url + "?view=skills")
        await pg.get_by_test_id("skills-wall-card").first.wait_for()
        await pg.wait_for_timeout(700)
        # scroll so B NEW cards are in view (after Phase1 block)
        await pg.locator('[data-testid="skills-wall-card"][data-skill="flash-cut-video"]').scroll_into_view_if_needed()
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=str(OUT / SHOTS[2]))
        print("wrote", OUT / SHOTS[2])

        # 4) website chip on Explore
        await pg.get_by_test_id("skills-chip-website").click()
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=str(OUT / SHOTS[3]))
        print("wrote", OUT / SHOTS[3])

        # 5) commerce-strategist dialog (Phase2 B → Agent path)
        await pg.goto(app_url + "?view=skills")
        await pg.get_by_test_id("skills-wall-card").first.wait_for()
        await pg.locator('[data-testid="skills-wall-card"][data-skill="commerce-strategist"]').scroll_into_view_if_needed()
        await pg.locator('[data-testid="skills-wall-card"][data-skill="commerce-strategist"]').click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        await pg.wait_for_timeout(900)
        await dlg.screenshot(path=str(OUT / SHOTS[4]))
        print("wrote", OUT / SHOTS[4])
        await pg.keyboard.press("Escape")
        await dlg.wait_for(state="hidden")

        # 6) social Fashion UGC dialog (A upgrade regression)
        await pg.locator('[data-testid="skills-wall-card"][data-skill="social"]').scroll_into_view_if_needed()
        await pg.locator('[data-testid="skills-wall-card"][data-skill="social"]').click()
        await dlg.wait_for()
        await pg.wait_for_timeout(900)
        await dlg.screenshot(path=str(OUT / SHOTS[5]))
        print("wrote", OUT / SHOTS[5])

        await browser.close()


if __name__ == "__main__":
    print("Use: DESIGN_638_78_SHOOT=1 PYTHONPATH=tests:. pytest -q tests/test_design_638_78_shots.py -s", file=sys.stderr)
    sys.exit(2)
