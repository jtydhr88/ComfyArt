"""#533 / #494-3 e2e (mock only, $0): home 精选 + 用 Skill 快速开始 → SkillRunDialog;
+ → 技能 still chip-only. Set HOME_SKILLS_SHOTS=/dir for zh-light + en-dark PNGs."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("HOME_SKILLS_SHOTS")


async def _open(p, app_url, lang, theme):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')"
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("home-start-skill").wait_for()
    return browser, pg


async def _shot(pg, name: str) -> None:
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(600)
    await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"), full_page=False)


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_home_skills_open_dialog(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme)
        await pg.get_by_test_id("home-featured-card").first.wait_for()
        await pg.locator('[data-testid="home-featured-card"] img').first.wait_for()
        # landing shot with 精选 in view (below the skill grid)
        await pg.get_by_test_id("home-featured").scroll_into_view_if_needed()
        await pg.wait_for_timeout(400)
        await _shot(pg, f"home-featured-{lang}-{theme}")
        # also a shot that shows 用 Skill 快速开始 near top of that section
        await pg.get_by_test_id("home-start-skill").scroll_into_view_if_needed()
        await pg.wait_for_timeout(300)
        await _shot(pg, f"home-quickstart-{lang}-{theme}")

        # quick-start → dialog
        await pg.get_by_test_id("home-skill-card").first.click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        assert await dlg.count() == 1
        await _shot(pg, f"home-quickstart-dialog-{lang}-{theme}")
        await pg.keyboard.press("Escape")
        await dlg.wait_for(state="hidden")

        # featured → dialog with that preset
        await pg.get_by_test_id("home-featured").scroll_into_view_if_needed()
        # #588: featured tiles are the skill's washed case images (featured[]), so pick a template-type skill's tile
        card = pg.locator('[data-testid="home-featured-card"][data-skill="brand-identity-director"]').first
        skill = await card.get_attribute("data-skill")
        await card.click()
        await dlg.wait_for()
        assert await dlg.get_attribute("data-skill") == skill
        assert await pg.locator('[data-testid="skill-run-preset"]').count() > 0
        await _shot(pg, f"home-featured-dialog-{lang}-{theme}")
        await pg.keyboard.press("Escape")
        await browser.close()


async def test_plus_skill_still_chip_only(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh", "light")
        await pg.get_by_test_id("home-plus").click()
        await pg.get_by_test_id("home-plus-skills").click()
        row = pg.get_by_test_id("home-skill-row").first
        name = (await row.inner_text()).strip()
        await row.click()
        chip = pg.get_by_test_id("home-skill-chip")
        await chip.wait_for()
        assert name.split("\n")[0] in (await chip.inner_text())
        assert await pg.get_by_test_id("skill-run-dialog").count() == 0
        await _shot(pg, "home-plus-chip-zh-light")
        await browser.close()
