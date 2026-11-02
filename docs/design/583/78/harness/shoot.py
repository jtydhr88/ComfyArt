"""#583 #78 AFTER tip-pin — Skills header 1:1 gold (zh-light + en-dark + sticky + 3-col grid).

Prefer:
  DESIGN_583_78_SHOOT=1 PYTHONPATH=.. pytest -q tests/test_design_583_78_shots.py -s
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "left-ours"

SHOTS = [
    "AFTER-skills-header-zh-light.png",
    "AFTER-skills-header-en-dark.png",
    "AFTER-skills-sticky-scroll-zh-light.png",
    "AFTER-skills-grid-3col-zh-light.png",
]


async def _goto_skills(pg, *, lang: str, theme: str, app_url: str) -> None:
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        "localStorage.setItem('comfyart.rail.collapsed','0');"
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("rail-skills").wait_for()
    await pg.get_by_test_id("rail-skills").click()
    await pg.get_by_test_id("skills-page").wait_for()
    await pg.get_by_test_id("skills-chrome").wait_for()
    await pg.get_by_test_id("skills-wall-card").first.wait_for()
    await pg.wait_for_timeout(700)


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # 1) zh-light header + chips + top of 3-col wall
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
        pg = await ctx.new_page()
        await _goto_skills(pg, lang="zh", theme="light", app_url=app_url)
        chrome = pg.get_by_test_id("skills-chrome")
        wall = pg.get_by_test_id("skills-wall")
        cbox = await chrome.bounding_box()
        wbox = await wall.bounding_box()
        assert cbox and wbox
        # crop: main skills area (skip rail) covering chrome through first card row
        clip = {
            "x": 240,
            "y": 0,
            "width": 1040,
            "height": min(800, max(420, int(wbox["y"] + 220))),
        }
        await pg.screenshot(path=str(OUT / SHOTS[0]), clip=clip)
        print("wrote", OUT / SHOTS[0], "chrome_h=", round(cbox["height"], 1))

        # measure grid cols @ content ~920
        cols = await pg.evaluate(
            """() => {
              const wall = document.querySelector('[data-testid="skills-wall"]');
              const cards = [...wall.querySelectorAll('[data-testid="skills-wall-card"]')];
              if (!cards.length) return null;
              const tops = new Map();
              for (const c of cards) {
                const r = c.getBoundingClientRect();
                const k = Math.round(r.top);
                tops.set(k, (tops.get(k) || 0) + 1);
              }
              const firstRow = Math.min(...tops.keys());
              const n = tops.get(firstRow);
              const w = cards[0].getBoundingClientRect().width;
              return {cols: n, cardW: Math.round(w), wallW: Math.round(wall.getBoundingClientRect().width)};
            }"""
        )
        print("grid@", cols)
        assert cols and cols["cols"] == 3 and 280 <= cols["cardW"] <= 310, cols

        # 4) dedicated 3-col grid crop (wall only)
        await pg.screenshot(
            path=str(OUT / SHOTS[3]),
            clip={
                "x": 240,
                "y": max(0, wbox["y"] - 8),
                "width": 1040,
                "height": min(520, 800 - max(0, wbox["y"] - 8)),
            },
        )
        print("wrote", OUT / SHOTS[3])

        # 3) sticky: scroll list; chrome y must stay put
        y0 = (await chrome.bounding_box())["y"]
        await pg.get_by_test_id("skills-scroll").evaluate("el => { el.scrollTop = 600; }")
        await pg.wait_for_timeout(400)
        y1 = (await chrome.bounding_box())["y"]
        scroll_top = await pg.get_by_test_id("skills-scroll").evaluate("el => el.scrollTop")
        print("sticky chrome y0=", y0, "y1=", y1, "scrollTop=", scroll_top)
        assert abs(y1 - y0) < 1 and scroll_top >= 500
        await pg.screenshot(path=str(OUT / SHOTS[2]), clip=clip)
        print("wrote", OUT / SHOTS[2])
        await ctx.close()

        # 2) en-dark header
        ctx2 = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
        pg2 = await ctx2.new_page()
        await _goto_skills(pg2, lang="en", theme="dark", app_url=app_url)
        title = await pg2.locator(".ca-skills__head h1").inner_text()
        assert title.strip() == "Skills", title
        cbox2 = await pg2.get_by_test_id("skills-chrome").bounding_box()
        wbox2 = await pg2.get_by_test_id("skills-wall").bounding_box()
        assert cbox2 and wbox2
        await pg2.screenshot(
            path=str(OUT / SHOTS[1]),
            clip={
                "x": 240,
                "y": 0,
                "width": 1040,
                "height": min(800, max(420, int(wbox2["y"] + 220))),
            },
        )
        print("wrote", OUT / SHOTS[1])
        await ctx2.close()
        await browser.close()


if __name__ == "__main__":
    raise SystemExit("Use: DESIGN_583_78_SHOOT=1 pytest -q tests/test_design_583_78_shots.py -s")
