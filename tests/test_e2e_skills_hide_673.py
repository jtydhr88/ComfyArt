"""#673/#735 e2e (mock only, $0): the remaining hidden Phase2 D-group skills appear nowhere on home (featured, chips, + → 技能) or the
Skills page (every chip). C-group is listed after #735. Set HIDE673_SHOTS=/dir for PNGs."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_skills_hide_673 import HIDDEN, MAIN_ORDER_45 as MAIN_ORDER_40

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("HIDE673_SHOTS")
SEL = ",".join(f'[data-skill="{h}"]' for h in HIDDEN)


async def _shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await pg.wait_for_timeout(600)
        await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"), full_page=False)


async def _full_shot(pg, name):
    """Whole page in one PNG: grow the viewport to the tallest scroll container so the waterfall / grid is all in view."""
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(600)
    h = await pg.evaluate("Math.min(16000, Math.max(...[...document.querySelectorAll('*')].map(e => e.scrollHeight - e.clientHeight + innerHeight)))")
    await pg.set_viewport_size({"width": 1440, "height": int(h)})
    await pg.wait_for_timeout(1500)  # lazy images in the newly visible rows
    await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"))
    await pg.set_viewport_size({"width": 1440, "height": 900})
    await pg.wait_for_timeout(300)


def _skill_names(lang):
    """id -> display name in `lang` (skills.ts name: t('key') + src/locales)."""
    loc = json.loads((ROOT / f"src/locales/{lang}.json").read_text())
    src = (ROOT / "src/skills.ts").read_text()
    return {m[0]: loc[m[1]] for m in re.findall(r"\{ id: '([a-z0-9-]+)', name: t\('([\w.]+)'\)", src)}


async def _slash(pg, q):
    box = pg.locator(".ca-composer__input")
    await box.fill("/" + q)
    await pg.wait_for_timeout(300)
    menu = pg.get_by_test_id("slash-menu")
    return [await b.get_attribute("data-skill") for b in await menu.locator("button").all()] if await menu.count() else []


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_composer_slash_picker_hides_deferred(app_url, lang, theme):  # noqa: F811
    names = _skill_names(lang)
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
        await pg.goto(app_url + f"?project=p673slash{lang}&new=1")
        await pg.locator(".ca-composer__input").wait_for()
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape")
                await pg.wait_for_timeout(300)
        first = await _slash(pg, "")
        assert first == MAIN_ORDER_40[:8], first  # '/' lists listed skills only, main order
        assert "ppt-visual" in await _slash(pg, "ppt")  # #735 C unhidden
        assert "yingzao" not in await _slash(pg, "ying")
        assert "yingzao" not in await _slash(pg, "营造")
        for h in HIDDEN:  # searching a hidden skill by its own name never offers it
            got = await _slash(pg, names[h].split()[0])
            assert not set(got) & set(HIDDEN), (h, got)
        for sid in ("poster", "brand", "product"):  # other skills still found by name
            assert sid in await _slash(pg, names[sid].split()[0]), sid
        await browser.close()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_hidden_skills_absent_home_and_skills_page(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
        await pg.goto(app_url)
        await pg.get_by_test_id("home-featured-card").first.wait_for()
        await pg.get_by_test_id("home-featured").scroll_into_view_if_needed()
        await pg.wait_for_timeout(400)
        assert await pg.locator(SEL).count() == 0
        await _shot(pg, f"home-featured-{lang}-{theme}")
        await pg.evaluate("document.querySelectorAll('*').forEach(e => { if (e.scrollTop) e.scrollTop = 0 })")
        await _full_shot(pg, f"home-foryou-full-{lang}-{theme}")
        for chip in await pg.locator('[data-testid^="home-chip-"]').all():
            await chip.click()
            await pg.wait_for_timeout(150)
            assert await pg.locator(SEL).count() == 0, await chip.get_attribute("data-testid")
        await pg.reload()
        await pg.get_by_test_id("home-plus").wait_for(state="visible")
        await pg.get_by_test_id("home-plus").click()
        await pg.get_by_test_id("home-plus-skills").click()
        rows = pg.get_by_test_id("home-skill-row")
        await rows.first.wait_for()
        ids = [await r.get_attribute("data-skill") for r in await rows.all()]
        assert ids == MAIN_ORDER_40, ids
        await pg.keyboard.press("Escape")

        await pg.get_by_test_id("rail-skills").click()
        await pg.get_by_test_id("skills-wall").wait_for()
        await pg.wait_for_timeout(400)
        wall = [await c.get_attribute("data-skill") for c in await pg.locator('[data-testid="skills-wall"] [data-testid="skills-wall-card"]').all()]
        assert wall == MAIN_ORDER_40, wall
        await _shot(pg, f"skills-page-{lang}-{theme}")
        await _full_shot(pg, f"skills-page-full-{lang}-{theme}")
        for chip in await pg.locator('[data-testid^="skills-chip-"]').all():
            await chip.click()
            await pg.wait_for_timeout(150)
            assert await pg.locator(SEL).count() == 0, await chip.get_attribute("data-testid")
        if lang == "zh":
            web = pg.get_by_test_id("skills-chip-website")
            if await web.count():
                await web.click()
                await pg.wait_for_timeout(300)
                await _shot(pg, f"skills-chip-website-{lang}-{theme}")
        assert not errors, errors
        await browser.close()
