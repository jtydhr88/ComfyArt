"""#637 #78 AFTER — B NEW5 SkillRunDialog shots (all 5 × zh-light + en-dark).
Run: DESIGN_637_78_SHOOT=1 PYTHONPATH=tests:. /workspace/.venv-589/bin/pytest -q docs/design/637/78/harness/shoot.py -s
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parents[1] / "after"

SKILLS = [
    "flash-cut-video",
    "style-transfer",
    "person-swap",
    "commerce-strategist",
    "lifestyle-scene",
]
COMBOS = [("zh", "light"), ("en", "dark")]
CAT = {
    "flash-cut-video": "ads",
    "style-transfer": "branding",
    "person-swap": "ecommerce",
    "commerce-strategist": "ecommerce",
    "lifestyle-scene": "ecommerce",
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
        chip = pg.get_by_test_id(f"skills-chip-{CAT[sid]}")
        if await chip.count():
            await chip.click()
            await pg.wait_for_timeout(500)
        card = pg.locator(f'[data-testid="skills-wall-card"][data-skill="{sid}"]')
    await card.first.wait_for(timeout=20_000)
    await card.first.scroll_into_view_if_needed()
    await card.first.click()
    dlg = pg.get_by_test_id("skill-run-dialog")
    await dlg.wait_for(timeout=10_000)
    assert await dlg.get_attribute("data-skill") == sid
    await pg.get_by_test_id("skill-run-preset").first.wait_for(timeout=10_000)
    # wait for left-column media (remote raw.githubusercontent.com wash pins)
    stage = dlg.locator('[data-testid="skill-examples"], [data-testid="skill-run-examples"], .skill-examples, img, video').first
    try:
        await stage.wait_for(timeout=15_000)
    except Exception:
        pass
    # allow remote webp/mp4 to paint (no gray placeholder)
    await pg.wait_for_timeout(2500)
    # if video present, wait for readyState
    vids = dlg.locator("video")
    if await vids.count():
        await vids.first.evaluate(
            """(v) => new Promise((res) => {
              if (v.readyState >= 2) return res();
              v.addEventListener('loadeddata', () => res(), { once: true });
              setTimeout(res, 8000);
            })"""
        )
        await pg.wait_for_timeout(400)


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
                n = await pg.get_by_test_id("skill-run-preset").count()
                print("wrote", OUT / name, "presets=", n, "size=", (OUT / name).stat().st_size)
                assert n >= 3, (sid, n)
                await ctx.close()
        await browser.close()


import pytest

pytestmark = [
    pytest.mark.skipif(os.environ.get("DESIGN_637_78_SHOOT") != "1", reason="set DESIGN_637_78_SHOOT=1"),
    pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs dist"),
]


@pytest.mark.asyncio
async def test_637_78_shoot(app_url):  # noqa: F811
    await capture(app_url)
    for sid in SKILLS:
        for lang, theme in COMBOS:
            p = OUT / shot_name(sid, lang, theme)
            assert p.is_file() and p.stat().st_size > 1000, p
