"""#576 #78 AFTER tip-pin — template select ring image-only; title outside.

Prefer:
  DESIGN_576_78_SHOOT=1 PYTHONPATH=tests /workspace/.venv-589/bin/python -m pytest -q tests/test_design_576_78_shots.py -s
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "left-ours"

SHOTS = [
    "AFTER-preset-selected-zh-light.png",
    "AFTER-preset-unselected-zh-light.png",
    "AFTER-preset-selected-en-dark.png",
    "AFTER-preset-unselected-en-dark.png",
    "AFTER-template-grid-zh-light.png",
    "AFTER-template-grid-en-dark.png",
]


async def _open_character(pg, app_url: str, lang: str, theme: str):
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        "localStorage.setItem('comfyart.rail.collapsed','0');"
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("home-start-skill").wait_for()
    # open skills wall → character sheet (has many template presets)
    await pg.get_by_test_id("rail-skills").click()
    await pg.get_by_test_id("skills-wall-card").first.wait_for()
    card = pg.locator('[data-testid="skills-wall-card"][data-skill="character"]')
    if await card.count() == 0:
        card = pg.locator('[data-skill="character"]')
    await card.first.locator(".ca-swall__cover").click()
    dlg = pg.get_by_test_id("skill-run-dialog")
    await dlg.wait_for()
    await pg.get_by_test_id("skill-run-presets").wait_for()
    await pg.wait_for_timeout(500)
    return dlg


async def _shot_pair(pg, prefix: str):
    tiles = pg.locator(".ca-skillrun__tile")
    assert await tiles.count() >= 2
    # ensure first selected, second not
    first = tiles.nth(0)
    second = tiles.nth(1)
    await first.get_by_test_id("skill-run-preset").click()
    await pg.wait_for_timeout(200)
    assert await first.get_by_test_id("skill-run-preset").get_attribute("aria-checked") == "true"
    assert await second.get_by_test_id("skill-run-preset").get_attribute("aria-checked") != "true"

    async def crop_tile(tile, name: str, pad: int = 12):
        box = await tile.bounding_box()
        assert box
        await pg.screenshot(
            path=str(OUT / name),
            clip={
                "x": max(0, box["x"] - pad),
                "y": max(0, box["y"] - pad),
                "width": box["width"] + pad * 2,
                "height": box["height"] + pad * 2,
            },
        )
        print("wrote", OUT / name, "size", (OUT / name).stat().st_size)

    await crop_tile(first, f"AFTER-preset-selected-{prefix}.png")
    await crop_tile(second, f"AFTER-preset-unselected-{prefix}.png")

    # grid overview (first 2x2-ish area)
    grid = pg.locator(".ca-skillrun__grid")
    box = await grid.bounding_box()
    assert box
    await pg.screenshot(
        path=str(OUT / f"AFTER-template-grid-{prefix}.png"),
        clip={
            "x": max(0, box["x"] - 8),
            "y": max(0, box["y"] - 8),
            "width": min(720, box["width"] + 16),
            "height": min(640, box["height"] + 16),
        },
    )
    print("wrote", OUT / f"AFTER-template-grid-{prefix}.png")


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        ctx = await browser.new_context(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        pg = await ctx.new_page()
        await _open_character(pg, app_url, "zh", "light")
        await _shot_pair(pg, "zh-light")
        await ctx.close()

        ctx2 = await browser.new_context(viewport={"width": 1440, "height": 960}, device_scale_factor=1)
        pg2 = await ctx2.new_page()
        await _open_character(pg2, app_url, "en", "dark")
        await _shot_pair(pg2, "en-dark")
        await ctx2.close()
        await browser.close()
