"""#748 e2e (mock only, $0): media[]-driven left renderer → 当前模板 wiring (click only, hover doesn't change it),
template-class Start disabled look, and video media actually plays. QA748_SHOTS=/dir writes L/R-ready shots."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("QA748_SHOTS")


async def _open(p, app_url, sid, lang, theme):  # noqa: F811
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    await pg.goto(app_url)
    await pg.get_by_test_id("rail-skills").click()
    await pg.get_by_test_id("skills-wall").wait_for()
    card = pg.locator(f'[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="{sid}"]')
    await card.scroll_into_view_if_needed()
    await card.hover()
    await card.get_by_test_id("skills-card-try").click()
    dlg = pg.locator(f'[data-testid="skill-run-dialog"][data-skill="{sid}"]')
    await dlg.wait_for(timeout=10000)
    return browser, pg, dlg


def _shot(name):
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    return str(Path(SHOTS) / name)


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "light"), ("zh", "dark"), ("en", "dark")])
@pytest.mark.parametrize("sid", ["packaging-design-director", "motion-poster-generator"])
async def test_skillrun_748(app_url, sid, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg, dlg = await _open(p, app_url, sid, lang, theme)
        go = dlg.get_by_test_id("skill-run-go")
        assert await go.get_attribute("aria-disabled") == "true", sid  # template-class: required empty → disabled look
        tiles = dlg.get_by_test_id("skill-run-preset")
        n = await tiles.count()
        if n >= 2:
            name0 = await dlg.get_by_test_id("skill-run-current-name").inner_text()
            await tiles.nth(1).hover()
            await pg.wait_for_timeout(400)
            assert await dlg.get_by_test_id("skill-run-current-name").inner_text() == name0  # hover never changes 当前模板
            if SHOTS:
                await pg.screenshot(path=_shot(f"748-{sid}-{lang}-{theme}-hover.png"))
            await tiles.nth(1).click()
            want = await tiles.nth(1).locator(".ca-skillrun__presetname").inner_text()
            assert await dlg.get_by_test_id("skill-run-current-name").inner_text() == want  # click drives name
            thumb = await dlg.get_by_test_id("skill-run-current-thumb").locator("img").get_attribute("src")
            tile_img = await tiles.nth(1).locator(".ca-skillrun__presetimg > img").get_attribute("src")
            assert thumb == tile_img
            if sid == "motion-poster-generator":  # #748 raw: per-template form — 首尾帧动画 adds its own start_frame upload
                assert await dlg.locator("#skill-run-start_frame").count() == 1
                await tiles.nth(0).click()
                assert await dlg.locator("#skill-run-start_frame").count() == 0
                await tiles.nth(1).click()
            assert await dlg.get_by_test_id("skill-run-current-usage").count() == 0  # usedCount 0 ⇒ usage line hidden
            assert await dlg.get_by_test_id("skill-run-meta").get_attribute("data-used") == "0"  # follows the selected template
            await pg.mouse.move(5, 5)
        # video media plays (preset hover video or example stage video)
        vids = dlg.locator("video")
        if await vids.count():
            v = vids.first
            await v.evaluate("v => { v.muted = true; return v.play().catch(() => {}) }")
            await pg.wait_for_timeout(1500)
            t = await v.evaluate("v => v.currentTime")
            assert t > 0, (sid, "video did not play")
        await pg.wait_for_timeout(500)
        if SHOTS:
            await pg.screenshot(path=_shot(f"748-{sid}-{lang}-{theme}.png"))
        await browser.close()


async def test_used_count_plus_one_on_successful_start_748(app_url):  # noqa: F811
    """#748 QA: a successful Start records +1 for the selected template (our own stats), shown as 已使用 1 次 next open."""
    async with pw.async_playwright() as p:
        browser, pg, dlg = await _open(p, app_url, "packaging-design-director", "zh", "light")
        assert await pg.evaluate("localStorage.getItem('comfyart.skillTemplateUsage')") in (None, "{}")
        await dlg.get_by_test_id("skill-run-preset").nth(1).click()
        await dlg.locator('input[type="file"]').first.set_input_files(str(Path(__file__).parent / "fixtures/ma_subject_691.png"))
        await pg.wait_for_function("() => !document.querySelector('[data-testid=skill-run-go]').disabled")
        txt = dlg.locator("textarea[data-key], input[data-key]:not([type=file])")
        for i in range(await txt.count()):
            await txt.nth(i).fill("测试 748")
        assert await dlg.get_by_test_id("skill-run-go").get_attribute("data-missing") is None
        await dlg.get_by_test_id("skill-run-go").click()
        await pg.wait_for_function("(localStorage.getItem('comfyart.skillTemplateUsage')||'').includes('packaging-design-director/')")
        used = await pg.evaluate("JSON.parse(localStorage.getItem('comfyart.skillTemplateUsage'))")
        assert list(used.values()) == [1] and list(used)[0].startswith("packaging-design-director/"), used
        await browser.close()
