"""#687 e2e (mock only, $0): the live skill dialogs render the hard-coded Lovart field spec (tests/lovart_fields_687.py)
— keys, types, required stars, upload kind, maxlength, label and EN placeholder copy — in zh-light and en-dark.
QA687_SHOTS=/dir writes skill-fields-<id>-<lang>-<theme>.png for every changed dialog."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from tests.lovart_fields_687 import CHANGED, SPEC

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("QA687_SHOTS")
READ = """dlg => [...dlg.querySelectorAll('[data-testid="skill-run-field"]')].map(f => {
  const box = f.closest('.ca-skillrun__field'); const lab = box.querySelector('.ca-skillform__label')
  const inp = f.matches('input,textarea,select') ? f : null
  return { key: f.dataset.key, type: f.dataset.type, required: f.getAttribute('aria-required') === 'true',
    accept: f.dataset.type === 'image' ? f.dataset.accept : null, star: !!lab.querySelector('.ca-skillrun__req'),
    max: inp && inp.maxLength > 0 ? inp.maxLength : null, label: lab.childNodes[0].textContent,
    ph: inp ? inp.getAttribute('placeholder') || null : null,
    fileAccept: box.querySelector('input[type=file]')?.getAttribute('accept') ?? null }
})"""


async def _page(p, lang, theme):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    return browser, pg


async def _check(pg, sid, lang):
    card = pg.locator(f'[data-testid="skills-wall"] [data-testid="skills-wall-card"][data-skill="{sid}"]')
    await card.scroll_into_view_if_needed()
    await card.hover()
    await card.get_by_test_id("skills-card-try").click()
    dlg = pg.locator(f'[data-testid="skill-run-dialog"][data-skill="{sid}"]')
    await dlg.wait_for(timeout=10000)
    got = await dlg.evaluate(READ)
    want = SPEC[sid]
    assert [g["key"] for g in got] == [w[0] for w in want], sid
    for g, (key, typ, req, acc, mx, zh, en, ph_en) in zip(got, want):
        assert (g["type"], g["required"], g["star"], g["accept"], g["max"]) == (typ, req, req, acc, mx), (sid, key, g)
        assert g["label"] == (zh if lang == "zh" else en), (sid, key, g["label"])
        if lang == "en":
            assert g["ph"] == ph_en, (sid, key, g["ph"])
        if typ == "image":
            assert g["fileAccept"] == ("video/*" if acc == "video" else "image/*"), (sid, key)
    go = pg.get_by_test_id("skill-run-go")
    assert await go.is_enabled(), sid  # #687: Start always clickable; validation runs on click
    assert await dlg.get_by_test_id("skill-run-field-error").count() == 0, sid  # no errors on open
    if sid == "motion":
        assert await dlg.get_by_test_id("skill-run-current").count() == 0  # #687: off-topic templates removed → no 模板 row
        assert await dlg.get_by_test_id("skill-run-preset").count() == 0
        from tests.lovart_fields_687 import MOTION_TITLE
        assert MOTION_TITLE[lang] in await dlg.inner_text()
    return dlg


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_skill_dialog_fields_match_lovart_687(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, lang, theme)
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.goto(app_url)
        await pg.get_by_test_id("rail-skills").click()
        await pg.get_by_test_id("skills-wall").wait_for()
        for sid in [*CHANGED, "product", "thumbnail", "multi-angle"]:
            dlg = await _check(pg, sid, lang)
            if SHOTS and sid in CHANGED:
                Path(SHOTS).mkdir(parents=True, exist_ok=True)
                await pg.wait_for_timeout(700)
                await pg.screenshot(path=str(Path(SHOTS) / f"skill-fields-{sid}-{lang}-{theme}.png"))
            await pg.keyboard.press("Escape")
            await dlg.wait_for(state="detached")
        assert not errors, errors
        await browser.close()


async def test_motion_featured_03_removed_687(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, "zh", "light")
        await pg.goto(app_url)
        await pg.get_by_test_id("home-featured-card").first.wait_for()
        html = await pg.content()
        assert "580/featured-v1/motion/03.webp" not in html
        await browser.close()


async def test_old_draft_and_link_keys_open_empty_687(app_url):  # noqa: F811
    """#687 decision: no old→new mapping. A stored old-key draft and an old-key link must not throw, must not lose existing content (stored draft kept intact); dialogs open empty."""
    import json
    from tests.lovart_fields_687 import OLD_KEYS_687
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, "en", "dark")
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.add_init_script("localStorage.setItem('comfyart.skillDraft.brand', " + json.dumps(json.dumps(OLD_KEYS_687["brand"])) + ")")
        qs = "&".join(f"{k}=x" for k in [*OLD_KEYS_687["brand"], *OLD_KEYS_687["motion"]])
        await pg.goto(app_url + "?" + qs)
        await pg.get_by_test_id("rail-skills").click()
        await pg.get_by_test_id("skills-wall").wait_for()
        for sid in ("brand", "motion"):
            dlg = await _check(pg, sid, "en")
            vals = await dlg.evaluate("""d => [...d.querySelectorAll('[data-testid="skill-run-field"]')].map(f =>
                [f.dataset.key, f.matches('input,textarea') ? f.value : (f.querySelector('img,video') ? 'media' : '')])""")
            assert vals == [[k, ""] for k, *_ in SPEC[sid]], (sid, vals)
            await pg.keyboard.press("Escape")
            await dlg.wait_for(state="detached")
        # nothing is lost: the stored old draft is left intact (not wiped / rewritten) after opening the dialogs
        kept = await pg.evaluate("localStorage.getItem('comfyart.skillDraft.brand')")
        assert kept is not None and json.loads(kept) == OLD_KEYS_687["brand"], kept
        # old-key ?skill= handoff link: lands in a project without throwing
        await pg.goto(app_url + "?skill=brand&mode=agent&ask=Old%20brand&brandInfo=Old&brandAssets=%2Fview%3Ff%3Dold.png")
        await pg.wait_for_timeout(1500)
        assert not errors, errors
        await browser.close()


async def test_motion_validates_only_after_start_click_687(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, "zh", "light")
        await pg.goto(app_url)
        await pg.get_by_test_id("rail-skills").click()
        await pg.get_by_test_id("skills-wall").wait_for()
        dlg = await _check(pg, "motion", "zh")
        url0 = pg.url
        await pg.get_by_test_id("skill-run-go").click()
        errs = await dlg.get_by_test_id("skill-run-field-error").evaluate_all("es => es.map(e => e.dataset.key)")
        assert errs == ["refVideo", "remakeBrief"], errs
        assert pg.url == url0  # nothing started
        await dlg.locator('[data-testid="skill-run-field"][data-key="remakeBrief"]').fill("swap product")
        errs = await dlg.get_by_test_id("skill-run-field-error").evaluate_all("es => es.map(e => e.dataset.key)")
        assert errs == ["refVideo"], errs
        if SHOTS:
            await pg.screenshot(path=str(Path(SHOTS) / "skill-fields-motion-after-start-zh-light.png"))
        await browser.close()
