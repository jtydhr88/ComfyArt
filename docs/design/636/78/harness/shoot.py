"""#636 #78 AFTER — C deferred5 soft wash SkillRunDialog shots (zh-light + en-dark).
Examples-only left (gold isomorphic); hardMax counts; right preset <select>.
Run: DESIGN_636_78_SHOOT=1 PYTHONPATH=tests:. /workspace/.venv-589/bin/pytest -q docs/design/636/78/harness/shoot.py -s
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parents[1] / "after"

# All C5 × zh-light + en-dark
SKILLS = ["naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce"]
COMBOS = [("zh", "light"), ("en", "dark")]
HARD_MAX = {
    "naive-illustration": "4",
    "logo-abstract": "11",
    "photo-split-poster": "1",
    "ppt-visual": "1",
    "promo-ecommerce": "4",
}
CAT = {
    "naive-illustration": "social",
    "logo-abstract": "branding",
    "photo-split-poster": "ads",
    "ppt-visual": "website",
    "promo-ecommerce": "ecommerce",
}


def shot_name(sid: str, lang: str, theme: str) -> str:
    return f"after-{sid}-dialog-{lang}-{theme}.png"


async def _open_skill(pg, app_url: str, sid: str, lang: str, theme: str) -> None:
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        "localStorage.setItem('comfyart.rail.collapsed','0');"
    )
    await pg.goto(app_url + "?view=skills")
    await pg.get_by_test_id("skills-wall-card").first.wait_for(timeout=30_000)
    card = pg.locator(f'[data-testid="skills-wall-card"][data-skill="{sid}"]')
    if await card.count() == 0:
        cat = CAT.get(sid)
        if cat:
            chip = pg.get_by_test_id(f"skills-chip-{cat}")
            if await chip.count():
                await chip.click()
                await pg.wait_for_timeout(400)
        card = pg.locator(f'[data-testid="skills-wall-card"][data-skill="{sid}"]')
    await card.first.wait_for(timeout=20_000)
    await card.first.scroll_into_view_if_needed()
    await card.first.click()
    dlg = pg.get_by_test_id("skill-run-dialog")
    await dlg.wait_for(timeout=10_000)
    assert await dlg.get_attribute("data-skill") == sid
    sel = pg.get_by_test_id("skill-run-preset-select")
    if await sel.count():
        await sel.wait_for(timeout=10_000)
    await pg.get_by_test_id("skill-run-examples").wait_for(timeout=15_000)
    await pg.wait_for_timeout(600)


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for sid in SKILLS:
            for lang, theme in COMBOS:
                name = shot_name(sid, lang, theme)
                ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
                pg = await ctx.new_page()
                await _open_skill(pg, app_url, sid, lang, theme)
                dlg = pg.get_by_test_id("skill-run-dialog")
                await dlg.screenshot(path=str(OUT / name))
                n_left = await pg.get_by_test_id("skill-run-preset").count()
                n_sel = await pg.get_by_test_id("skill-run-preset-select").count()
                ex = pg.get_by_test_id("skill-run-examples")
                count = await ex.get_attribute("data-count")
                want = HARD_MAX[sid]
                assert count == want, (sid, count, want)
                assert n_left == 0, (sid, "left presets must be hidden for Examples-only gold", n_left)
                assert n_sel == 1, (sid, "right preset select expected", n_sel)
                assert await pg.get_by_test_id("skill-run-presets").count() == 0, (sid, "presets radiogroup must be absent")
                left_attr = await pg.locator('.ca-skillrun__templates').get_attribute('data-left')
                assert left_attr == 'examples', (sid, left_attr)
                print("wrote", OUT / name, "examples=", count, "leftPresets=", n_left, "size=", (OUT / name).stat().st_size)
                await ctx.close()
        await browser.close()


import pytest

pytestmark = [
    pytest.mark.skipif(os.environ.get("DESIGN_636_78_SHOOT") != "1", reason="set DESIGN_636_78_SHOOT=1"),
    pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs dist"),
]


@pytest.mark.asyncio
async def test_636_78_shoot(app_url):  # noqa: F811
    await capture(app_url)
    for sid in SKILLS:
        for lang, theme in COMBOS:
            p = OUT / shot_name(sid, lang, theme)
            assert p.is_file() and p.stat().st_size > 1000, p
