"""#573 #78 AFTER tip-pin — upscale resolution Pick collapsed value left-aligned.

Prefer:
  DESIGN_573_78_SHOOT=1 PYTHONPATH=tests /workspace/.venv-589/bin/python -m pytest -q tests/test_design_573_78_shots.py -s
"""
from __future__ import annotations

from pathlib import Path

from test_e2e_home_tools_537 import _PNG

OUT = Path(__file__).resolve().parents[1] / "left-ours"

SHOTS = [
    "AFTER-res-collapsed-zh-light.png",
    "AFTER-res-open-zh-light.png",
    "AFTER-res-collapsed-en-dark.png",
    "AFTER-res-open-en-dark.png",
    "AFTER-panel-zh-light.png",
    "AFTER-panel-en-dark.png",
]


async def _open_upscale(pg, app_url: str, lang: str, theme: str):
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        "localStorage.setItem('comfyart.rail.collapsed','0');"
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("home-tools").wait_for()
    async with pg.expect_file_chooser() as fc:
        await pg.get_by_test_id("home-tool-card-upscale").click()
    await (await fc.value).set_files({"name": "t.png", "mimeType": "image/png", "buffer": _PNG})
    panel = pg.locator(".ca-toolpanel[data-tool='upscale']")
    await panel.wait_for(state="visible", timeout=15000)
    await pg.locator(".tl-container").first.wait_for()
    await pg.wait_for_timeout(1500)
    return panel


async def _clip_union(*boxes, pad: int = 8):
    xs = [b["x"] for b in boxes]
    ys = [b["y"] for b in boxes]
    x1 = [b["x"] + b["width"] for b in boxes]
    y1 = [b["y"] + b["height"] for b in boxes]
    x0, y0 = min(xs) - pad, min(ys) - pad
    return {
        "x": max(0, x0),
        "y": max(0, y0),
        "width": max(x1) - x0 + pad,
        "height": max(y1) - y0 + pad,
    }


async def _pair(pg, app_url: str, lang: str, theme: str, suffix: str):
    panel = await _open_upscale(pg, app_url, lang, theme)
    pick = panel.locator("[data-res-pick] button.ca-pick")
    await pick.wait_for()
    await pick.evaluate("e => e.scrollIntoView({block:'center'})")
    await pg.wait_for_timeout(200)
    ta = await pick.evaluate("e => getComputedStyle(e).textAlign")
    assert ta == "left", ta
    txt = (await pick.inner_text()).strip()
    assert txt.startswith("2K"), txt
    pb = await pick.bounding_box()
    pan = await panel.bounding_box()
    assert pb and pan and pb["width"] > 40 and pb["height"] > 20, (pb, pan)
    print("pick box", pb, "panel", pan, "theme", theme, "text", txt)
    # collapsed: crop pick from page
    await pg.screenshot(path=str(OUT / f"AFTER-res-collapsed-{suffix}.png"), clip=await _clip_union(pb, pad=6))
    await pg.screenshot(path=str(OUT / f"AFTER-panel-{suffix}.png"), clip=await _clip_union(pan, pad=12))
    print("wrote collapsed+panel", suffix, (OUT / f"AFTER-res-collapsed-{suffix}.png").stat().st_size)
    await pick.click()
    menu = pg.locator(".ca-pick__menu")
    await menu.wait_for()
    await pg.wait_for_timeout(300)
    mb = await menu.bounding_box()
    pb2 = await pick.bounding_box()
    assert mb and pb2
    await pg.screenshot(path=str(OUT / f"AFTER-res-open-{suffix}.png"), clip=await _clip_union(pb2, mb, pad=8))
    print("wrote open", suffix, (OUT / f"AFTER-res-open-{suffix}.png").stat().st_size)


async def capture(app_url: str):
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for lang, theme, suffix in (("zh", "light", "zh-light"), ("en", "dark", "en-dark")):
            ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
            pg = await ctx.new_page()
            await _pair(pg, app_url, lang, theme, suffix)
            await ctx.close()
        await browser.close()
