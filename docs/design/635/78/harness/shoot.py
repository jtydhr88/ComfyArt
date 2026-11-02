"""#635 #78 AFTER — social SkillRunDialog Fashion UGC presets (zh/en × light/dark).
Run: DESIGN_635_78_SHOOT=1 PYTHONPATH=tests:. /workspace/.venv-589/bin/pytest -q docs/design/635/78/harness/shoot.py -s
Or via tests/test_design_635_78_shots.py
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parents[1] / "after"
SHOTS = [
    "after-social-dialog-fashion-ugc-zh-light.png",
    "after-social-dialog-fashion-ugc-en-light.png",
    "after-social-dialog-fashion-ugc-zh-dark.png",
    "after-social-dialog-fashion-ugc-en-dark.png",
]


async def _open_social(pg, app_url: str, lang: str, theme: str) -> None:
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        "localStorage.setItem('comfyart.rail.collapsed','0');"
    )
    await pg.goto(app_url + "?view=skills")
    # Skills wall: find social card
    card = pg.locator('[data-testid="skills-wall-card"][data-skill="social"]')
    # may need scroll / forYou
    await pg.get_by_test_id("skills-wall-card").first.wait_for(timeout=30_000)
    if await card.count() == 0:
        # try chip social
        chip = pg.get_by_test_id("skills-chip-social")
        if await chip.count():
            await chip.click()
            await pg.wait_for_timeout(300)
    await card.first.wait_for(timeout=15_000)
    await card.first.scroll_into_view_if_needed()
    await card.first.click()
    dlg = pg.get_by_test_id("skill-run-dialog")
    await dlg.wait_for(timeout=10_000)
    assert await dlg.get_attribute("data-skill") == "social"
    # wait Fashion UGC presets
    presets = pg.get_by_test_id("skill-run-preset")
    await presets.first.wait_for(timeout=10_000)
    n = await presets.count()
    assert n >= 2, n
    # ensure labels visible
    await pg.wait_for_timeout(500)


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    combos = [
        ("zh", "light", SHOTS[0]),
        ("en", "light", SHOTS[1]),
        ("zh", "dark", SHOTS[2]),
        ("en", "dark", SHOTS[3]),
    ]
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for lang, theme, name in combos:
            ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
            pg = await ctx.new_page()
            await _open_social(pg, app_url, lang, theme)
            dlg = pg.get_by_test_id("skill-run-dialog")
            await dlg.screenshot(path=str(OUT / name))
            print("wrote", OUT / name, "presets=", await pg.get_by_test_id("skill-run-preset").count())
            await ctx.close()
        await browser.close()


# pytest entry when collected as test module
import pytest

pytestmark = [
    pytest.mark.skipif(os.environ.get("DESIGN_635_78_SHOOT") != "1", reason="set DESIGN_635_78_SHOOT=1"),
    pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs dist"),
]


@pytest.mark.asyncio
async def test_635_78_shoot(app_url):  # noqa: F811
    import sys
    sys.path.insert(0, str(ROOT / "tests"))
    from test_e2e_comment_edit import app_url as _  # noqa: F401 — fixture from conftest chain
    await capture(app_url)
    for name in SHOTS:
        p = OUT / name
        assert p.is_file() and p.stat().st_size > 1000, p
