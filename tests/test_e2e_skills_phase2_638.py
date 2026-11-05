"""#638 Phase2-S5 Soft mount e2e (mock only, $0): Phase2 B after Phase1, website chip, commerce dialog→Agent, social Fashion UGC."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")

HOT_QUICK = ["product-tvc-advertisement-generator", "universal-multi-angle-grid", "brand-identity-director", "character-sheet-design", "logo-material-explorer", "packaging-design-director"]
PHASE2_B = [
    "flash-cut-video", "style-transfer", "person-swap",
    "commerce-strategist", "lifestyle-scene",
]


async def _open_home(p, app_url, lang="zh"):  # noqa: F811
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        "localStorage.setItem('comfyart.theme','light');"
        "localStorage.setItem('comfyart.rail.collapsed','0');"
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("home-start-skill").wait_for()
    return browser, pg


async def test_home_quickstart_phase1_and_website_chip(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open_home(p, app_url)
        cards = pg.get_by_test_id("home-skill-card")
        await cards.first.wait_for()
        assert await cards.count() == 6
        ids = await cards.evaluate_all("els => els.map(e => e.dataset.skill)")
        assert ids == HOT_QUICK
        # website chip lit (Phase1 mobile-ui/web-product; ppt-visual C HOLD may appear in filter)
        assert await pg.get_by_test_id("home-chip-website").count() == 1
        await pg.get_by_test_id("home-chip-website").click()
        shown = await pg.get_by_test_id("home-skill-card").evaluate_all("els => els.map(e => e.dataset.skill)")
        assert "mobile-app-visual-design" in shown and "web-product-visual-design" in shown
        # Soft mount does not require ppt-visual in the quick-start row
        await browser.close()


async def test_skills_explore_phase2_b_after_phase1(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open_home(p, app_url)
        await pg.goto(app_url + "?view=skills")
        await pg.get_by_test_id("skills-wall-card").first.wait_for()
        ids = await pg.get_by_test_id("skills-wall-card").evaluate_all("els => els.map(e => e.dataset.skill)")
        # Phase1 product first; B NEW5 appear after Phase1 block; social once
        assert ids[0] == "product-tvc-advertisement-generator"
        assert ids.count("rednote-cover-maker") == 1
        for sid in PHASE2_B:
            assert sid in ids, sid
        # Soft order among B: flash-cut → style-transfer → person-swap → commerce → lifestyle
        bpos = [ids.index(s) for s in PHASE2_B]
        assert bpos == sorted(bpos)
        # #735: C unhidden on the wall; D still absent
        assert "naive-illustration" in ids and "ppt-visual" in ids
        assert "yingzao" not in ids and "fabric-collage" not in ids
        # website chip on Explore
        assert await pg.get_by_test_id("skills-chip-website").count() == 1
        await browser.close()


async def test_commerce_strategist_dialog_to_agent_and_social_ugc(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open_home(p, app_url, "en")
        await pg.goto(app_url + "?view=skills")
        await pg.get_by_test_id("skills-wall-card").first.wait_for()
        # Phase2 B: commerce-strategist text field → Agent (AC ≥1 dialog→Agent)
        await pg.locator('[data-testid="skills-wall-card"][data-skill="commerce-strategist"]').click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        assert await dlg.get_attribute("data-skill") == "commerce-strategist"
        await pg.locator('[data-testid="skill-run-field"][data-key="sellPoints"]').fill("3C earbuds — ANC, 30h battery, clear benefit ladder")
        await pg.get_by_test_id("skill-run-go").click()
        await pg.wait_for_url(re.compile(r"[?&]skill=commerce-strategist"), timeout=10_000)
        assert "mode=agent" in pg.url
        # Back home → social Fashion UGC presets regression
        await pg.goto(app_url + "?view=skills")
        await pg.locator('[data-testid="skills-wall-card"][data-skill="rednote-cover-maker"]').click()
        await dlg.wait_for()
        assert await dlg.get_attribute("data-skill") == "rednote-cover-maker"
        # #636 product lock: Examples-only (presets lack media) → no 「当前模板」 select
        assert await pg.get_by_test_id("skill-run-preset-select").count() == 0
        assert await pg.get_by_test_id("skill-run-current").count() == 0
        left = await pg.get_by_test_id("skill-run-examples").get_attribute("data-count")
        assert left is not None and int(left) >= 1
        await browser.close()
