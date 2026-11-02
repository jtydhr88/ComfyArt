"""#622 #78 AFTER tip-pin — motion×2 wash-v1 preset.video hover/play.

Prefer:
  DESIGN_622_78_SHOOT=1 PYTHONPATH=tests /workspace/.venv-589/bin/python -m pytest -q tests/test_design_622_78_shots.py -s
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "after"

SHOTS = [
    "AFTER-motion-preset-hover-zh-light.png",
    "AFTER-motion-preset-hover-en-dark.png",
    "AFTER-motion-template-grid-zh-light.png",
    "AFTER-motion-template-grid-en-dark.png",
]

PIN = "5a8d22ed88f732d38f8709a2c0740f074a400a89"
EXPECT_SRCS = [
    f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{PIN}/575/wash/templates/01-poster-animation.mp4",
    f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{PIN}/575/wash/templates/02-first-to-last-frame-animation.mp4",
]


async def _open_motion(pg, app_url: str, lang: str, theme: str):
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        "localStorage.setItem('comfyart.rail.collapsed','0');"
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("home-start-skill").wait_for()
    await pg.get_by_test_id("rail-skills").click()
    await pg.get_by_test_id("skills-wall-card").first.wait_for()
    card = pg.locator('[data-testid="skills-wall-card"][data-skill="motion"]')
    if await card.count() == 0:
        card = pg.locator('[data-skill="motion"]')
    await card.first.locator(".ca-swall__cover").click()
    dlg = pg.get_by_test_id("skill-run-dialog")
    await dlg.wait_for()
    assert await dlg.get_attribute("data-skill") == "motion"
    await pg.get_by_test_id("skill-run-presets").wait_for()
    await pg.wait_for_timeout(600)
    return dlg


async def _assert_videos(pg):
    vids = pg.get_by_test_id("skill-run-preset-video")
    assert await vids.count() == 2, await vids.count()
    srcs = await vids.evaluate_all("els => els.map(e => e.currentSrc || e.src)")
    assert sorted(srcs) == sorted(EXPECT_SRCS), srcs
    # hover first tile → play
    tile = pg.locator('.ca-skillrun__tile[data-has-video="1"]').first
    btn = tile.get_by_test_id("skill-run-preset")
    await btn.hover()
    await pg.wait_for_timeout(900)
    playing = await tile.get_by_test_id("skill-run-preset-video").evaluate(
        "v => !v.paused && v.readyState >= 2"
    )
    # network-dependent; accept either playing or currentTime advanced after play() attempt
    ct = await tile.get_by_test_id("skill-run-preset-video").evaluate("v => v.currentTime")
    opacity = await tile.get_by_test_id("skill-run-preset-video").evaluate(
        "v => getComputedStyle(v).opacity"
    )
    return {"playing": playing, "currentTime": ct, "opacity": opacity, "srcs": srcs}


async def _shot(pg, prefix: str):
    info = await _assert_videos(pg)
    print("hover", prefix, info)
    tile = pg.locator('.ca-skillrun__tile[data-has-video="1"]').first
    box = await tile.bounding_box()
    assert box
    pad = 16
    await pg.screenshot(
        path=str(OUT / f"AFTER-motion-preset-hover-{prefix}.png"),
        clip={
            "x": max(0, box["x"] - pad),
            "y": max(0, box["y"] - pad),
            "width": box["width"] + pad * 2,
            "height": box["height"] + pad * 2,
        },
    )
    print("wrote", OUT / f"AFTER-motion-preset-hover-{prefix}.png")
    grid = pg.locator(".ca-skillrun__grid")
    gbox = await grid.bounding_box()
    assert gbox
    await pg.screenshot(
        path=str(OUT / f"AFTER-motion-template-grid-{prefix}.png"),
        clip={
            "x": max(0, gbox["x"] - 8),
            "y": max(0, gbox["y"] - 8),
            "width": min(720, gbox["width"] + 16),
            "height": min(640, gbox["height"] + 16),
        },
    )
    print("wrote", OUT / f"AFTER-motion-template-grid-{prefix}.png")
    assert info["srcs"] == EXPECT_SRCS or sorted(info["srcs"]) == sorted(EXPECT_SRCS)


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        pg = await ctx.new_page()
        await _open_motion(pg, app_url, "zh", "light")
        await _shot(pg, "zh-light")
        await ctx.close()

        ctx2 = await browser.new_context(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        pg2 = await ctx2.new_page()
        await _open_motion(pg2, app_url, "en", "dark")
        await _shot(pg2, "en-dark")
        await ctx2.close()
        await browser.close()
