"""#623 #78 AFTER tip-pin — new6 Skill.video hover muted-loop (Home + Skills wall).

Prefer:
  DESIGN_623_78_SHOOT=1 PYTHONPATH=tests /workspace/.venv-589/bin/python -m pytest -q tests/test_design_623_78_shots.py -s
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "after"

SHOTS = [
    "AFTER-new6-home-hover-zh-light.png",
    "AFTER-new6-home-hover-en-dark.png",
    "AFTER-new6-home-grid-zh-light.png",
    "AFTER-new6-home-grid-en-dark.png",
]

PIN = "d03ea7938877d084c201a94ef51f943dd0e061b9"
NEW6 = [
    "multi-angle",
    "logo-material",
    "meta-ads",
    "mobile-ui",
    "web-product",
    "marketing-campaign",
]
EXPECT_SRC = {
    sid: f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{PIN}/594/wash/videos/{sid}.mp4"
    for sid in NEW6
}
# Home quick-start row is HOME_SKILL_ROW=6 of forYou; Phase1 order puts these two in the first 6.
HOME_VISIBLE = ["multi-angle", "logo-material"]


async def _open_home(pg, app_url: str, lang: str, theme: str):
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        "localStorage.setItem('comfyart.rail.collapsed','0');"
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("home-skill-grid").wait_for()
    await pg.wait_for_timeout(800)
    return pg


async def _assert_home_visible_videos(pg):
    found = {}
    for sid in HOME_VISIBLE:
        card = pg.locator(f'[data-testid="home-skill-card"][data-skill="{sid}"]')
        assert await card.count() >= 1, sid
        vid = card.get_by_test_id("home-skill-card-video")
        assert await vid.count() == 1, sid
        src = await vid.evaluate("v => (v.currentSrc || v.src || '').split('#')[0]")
        assert src == EXPECT_SRC[sid], (sid, src)
        found[sid] = src
    return found


async def _assert_skills_wall_new6(pg):
    await pg.get_by_test_id("rail-skills").click()
    wall = pg.get_by_test_id("skills-wall")
    await wall.wait_for()
    await pg.wait_for_timeout(600)
    found = {}
    for sid in NEW6:
        card = pg.locator(f'[data-testid="skills-wall-card"][data-skill="{sid}"]')
        assert await card.count() >= 1, sid
        assert await card.get_attribute("data-has-video") == "1", sid
        vid = card.get_by_test_id("skills-card-video")
        assert await vid.count() == 1, sid
        src = await vid.evaluate("v => (v.currentSrc || v.src || '').split('#')[0]")
        assert src == EXPECT_SRC[sid], (sid, src)
        found[sid] = src
    # hover multi-angle on wall (muted loop)
    card = pg.locator('[data-testid="skills-wall-card"][data-skill="multi-angle"]')
    await card.scroll_into_view_if_needed()
    await card.hover()
    await pg.wait_for_timeout(1100)
    info = await card.get_by_test_id("skills-card-video").evaluate(
        "v => ({ paused: v.paused, ready: v.readyState, ct: v.currentTime, opacity: getComputedStyle(v).opacity })"
    )
    # back to home for pairing shots
    await pg.get_by_test_id("rail-home").click()
    await pg.get_by_test_id("home-skill-grid").wait_for()
    await pg.wait_for_timeout(400)
    return {"srcs": found, "hover": info}


async def _shot(pg, prefix: str):
    home = await _assert_home_visible_videos(pg)
    wall = await _assert_skills_wall_new6(pg)
    print("home", prefix, home)
    print("wall-hover", prefix, wall["hover"])
    card = pg.locator('[data-testid="home-skill-card"][data-skill="multi-angle"]')
    await card.hover()
    await pg.wait_for_timeout(1100)
    info = await card.get_by_test_id("home-skill-card-video").evaluate(
        "v => ({ paused: v.paused, ready: v.readyState, ct: v.currentTime, opacity: getComputedStyle(v).opacity })"
    )
    print("home-hover", prefix, info)
    box = await card.bounding_box()
    assert box
    pad = 12
    await pg.screenshot(
        path=str(OUT / f"AFTER-new6-home-hover-{prefix}.png"),
        clip={
            "x": max(0, box["x"] - pad),
            "y": max(0, box["y"] - pad),
            "width": box["width"] + pad * 2,
            "height": box["height"] + pad * 2,
        },
    )
    print("wrote", OUT / f"AFTER-new6-home-hover-{prefix}.png")
    grid = pg.get_by_test_id("home-skill-grid")
    gbox = await grid.bounding_box()
    assert gbox
    await pg.screenshot(
        path=str(OUT / f"AFTER-new6-home-grid-{prefix}.png"),
        clip={
            "x": max(0, gbox["x"] - 8),
            "y": max(0, gbox["y"] - 8),
            "width": min(1100, gbox["width"] + 16),
            "height": min(720, gbox["height"] + 16),
        },
    )
    print("wrote", OUT / f"AFTER-new6-home-grid-{prefix}.png")
    assert set(wall["srcs"]) == set(NEW6)


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        pg = await ctx.new_page()
        await _open_home(pg, app_url, "zh", "light")
        await _shot(pg, "zh-light")
        await ctx.close()

        ctx2 = await browser.new_context(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        pg2 = await ctx2.new_page()
        await _open_home(pg2, app_url, "en", "dark")
        await _shot(pg2, "en-dark")
        await ctx2.close()
        await browser.close()
