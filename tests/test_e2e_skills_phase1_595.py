"""#595 Phase1-S5 mount e2e (mock only, $0): home quick-start hot order, website chip, new6 dialog→Agent project."""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")

HOT_QUICK = ["product", "multi-angle", "brand", "character", "logo-material", "packaging"]


async def _open_home(p, app_url, lang="zh"):  # noqa: F811
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.rail.collapsed','0');")
    await pg.goto(app_url)
    await pg.get_by_test_id("home-start-skill").wait_for()
    return browser, pg


async def test_home_quickstart_hot_order_and_website_chip(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open_home(p, app_url)
        cards = pg.get_by_test_id("home-skill-card")
        await cards.first.wait_for()
        assert await cards.count() == 6
        ids = await cards.evaluate_all("els => els.map(e => e.dataset.skill)")
        assert ids == HOT_QUICK
        # website chip lit on home explore chips
        assert await pg.get_by_test_id("home-chip-website").count() == 1
        await pg.get_by_test_id("home-chip-website").click()
        shown = await pg.get_by_test_id("home-skill-card").evaluate_all("els => els.map(e => e.dataset.skill)")
        assert set(shown) <= {"mobile-ui", "web-product", "ppt-visual", "product-website", "premium-website", "restaurant-website"}  # + #634 ppt-visual, #640 NEW19 website skills
        assert "mobile-ui" in shown and "web-product" in shown
        await browser.close()


async def test_multi_angle_carousel_and_brand_dialog_to_agent(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open_home(p, app_url, "en")
        # new6: horizontal examples carousel; #691 right pane = exactly Upload then Additional, zero preset UI
        await pg.locator('[data-testid="home-skill-card"][data-skill="multi-angle"]').click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        assert await dlg.get_attribute("data-skill") == "multi-angle"
        await pg.get_by_test_id("skill-run-example-thumb").first.wait_for()
        assert await pg.get_by_test_id("skill-run-examples").count() == 1
        assert await pg.get_by_test_id("skill-run-example-thumb").count() >= 2
        # #636/#666: left pane is examples-only
        assert await dlg.locator('[data-left="examples"]').count() == 1
        assert await pg.get_by_test_id("skill-run-preset").count() == 0
        assert await pg.get_by_test_id("skill-run-preset-chips").count() == 0
        fields = pg.get_by_test_id("skill-run-field")
        assert await fields.evaluate_all("fs => fs.map(f => [f.dataset.key, f.dataset.type])") == [["file", "image"], ["note", "textarea"]]
        assert await pg.locator('[data-key="note"]').get_attribute("placeholder") == "Anything you want to add? Uploading a reference image is recommended"
        await pg.keyboard.press("Escape")
        await dlg.wait_for(state="hidden")
        # Phase1 upgrade skill: dialog → new Agent project (AC ≥1)
        await pg.locator('[data-testid="home-skill-card"][data-skill="brand"]').click()
        await dlg.wait_for()
        await pg.locator('[data-testid="skill-run-field"][data-key="brandInfo"]').fill("Autumn launch kit")
        await pg.get_by_test_id("skill-run-go").click()
        await pg.wait_for_url(re.compile(r"[?&]skill=brand"), timeout=10_000)
        assert "mode=agent" in pg.url
        await browser.close()


async def test_multi_angle_upload_reaches_handoff_ref_691(app_url):  # noqa: F811
    # #691/#693: the Upload block (key `file`) feeds the same `ref` handoff param the old 主体图片 field did
    from pathlib import Path
    async with pw.async_playwright() as p:
        browser, pg = await _open_home(p, app_url, "en")
        await pg.locator('[data-testid="home-skill-card"][data-skill="multi-angle"]').click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        await dlg.locator('input[type="file"]').set_input_files(str(Path(__file__).parent / "fixtures/ma_subject_691.png"))
        await pg.wait_for_function("() => !document.querySelector('[data-testid=skill-run-go]').disabled")
        thumb = dlg.locator(".ca-gen__ref")
        await thumb.hover()
        assert await thumb.locator("img").count() == 1 and await thumb.get_by_title("Remove").count() == 1  # thumbnail + delete
        if os.environ.get("SHOTS_691"):
            await dlg.locator(".ca-skillrun__right").screenshot(path=os.environ["SHOTS_691"] + "/05-right-pane-after-upload-en.png")
        await pg.locator('[data-key="note"]').fill("PDP, white seamless")
        navs: list[str] = []
        pg.on("framenavigated", lambda f: navs.append(f.url))
        await pg.get_by_test_id("skill-run-go").click()
        for _ in range(50):
            if any("skill=multi-angle" in u for u in navs):
                break
            await pg.wait_for_timeout(200)
        u = next(u for u in navs if "skill=multi-angle" in u)
        assert re.search(r"[?&]ref=[^&]*skill-multi-angle-ma_subject_691\.png", u), u
        assert "mode=agent" in u and "PDP" in u
        await browser.close()
