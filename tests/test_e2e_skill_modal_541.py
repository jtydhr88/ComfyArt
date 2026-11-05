"""#541 e2e (mock only, $0): skill modal geometry (1112×820, 752|360, tiles 344×288, image ring 344×258, 22px zoom, 312 controls),
real meta line, zoom view, dashed upload, pinned submit gating."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_skill_cards_494 import _open

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")

BOX = "el => { const r = el.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), Math.round(r.x), Math.round(r.y)] }"


async def _modal(pg, skill):
    await pg.set_viewport_size({"width": 1440, "height": 960})
    await pg.locator(f'[data-skill="{skill}"] .ca-swall__cover').click()
    dlg = pg.get_by_test_id("skill-run-dialog")
    await dlg.wait_for()
    await pg.wait_for_timeout(300)
    return dlg


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_geometry(app_url, lang):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang)
        dlg = await _modal(pg, "brand-identity-director")  # #569: poster has no tiles now; brand is the template-grid fixture
        assert (await dlg.evaluate(BOX))[:2] == [1112, 820]
        assert (await dlg.locator(".ca-skillrun__left").evaluate(BOX))[0] == 752
        assert (await dlg.locator(".ca-skillrun__right").evaluate(BOX))[0] == 360
        tiles = pg.locator(".ca-skillrun__tile")
        assert await tiles.count() == 6
        assert (await tiles.first.evaluate(BOX))[:2] == [344, 288]
        assert (await pg.locator(".ca-skillrun__presetimg").first.evaluate(BOX))[:2] == [344, 258]
        a, b = await tiles.nth(0).evaluate(BOX), await tiles.nth(1).evaluate(BOX)
        assert b[2] - a[2] == 360  # 344 + gap 16
        assert (await pg.get_by_test_id("skill-run-current").locator(".ca-skillrun__currentrow").evaluate(BOX))[:2] == [312, 86]
        assert (await pg.get_by_test_id("skill-run-upload").evaluate(BOX))[:2] == [312, 140]
        go = pg.get_by_test_id("skill-run-go")
        g, r = await go.evaluate(BOX), await dlg.evaluate(BOX)
        assert g[:2] == [312, 36] and r[3] + r[1] - (g[3] + g[1]) == 24  # pinned to bottom
        meta = await pg.get_by_test_id("skill-run-meta").inner_text()
        assert meta == ("6 个模板" if lang == "zh" else "6 templates")
        bg = await dlg.locator(".ca-skillrun__right").evaluate("el => getComputedStyle(el).backgroundColor")
        assert bg == "rgb(245, 245, 245)"
        await browser.close()


async def test_zoom_select_and_gating(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh")
        await _modal(pg, "product-tvc-advertisement-generator")
        assert await pg.locator(".ca-skillrun__tile").count() == 7  # tiles follow presets[] (#748 raw: 7)
        ids = await pg.get_by_test_id("skill-run-preset").evaluate_all("bs => bs.map(b => b.dataset.preset)")
        assert ids == ["white", "lifestyle", "detail", "electronics", "food", "beauty", "t7"]  # #748: 7th raw template
        assert await pg.get_by_test_id("skill-run-meta").inner_text() == "7 个模板"
        tile = pg.locator(".ca-skillrun__tile").nth(1)
        await tile.hover()
        z = tile.get_by_test_id("skill-run-zoom")
        # measure after the 150ms scale(0.85→1) hover transition settles (was timing-dependent)
        await z.evaluate("el => Promise.all(el.getAnimations().map(a => a.finished))")
        assert (await z.evaluate(BOX))[:2] == [22, 22]
        await z.click()
        view = pg.get_by_test_id("skill-run-zoomview")
        await view.wait_for()
        await view.click()
        assert await view.count() == 0
        assert await pg.get_by_test_id("skill-run-dialog").count() == 1  # zoom close ≠ modal close
        await tile.get_by_test_id("skill-run-preset").click()
        assert await tile.get_by_test_id("skill-run-preset").get_attribute("aria-checked") == "true"
        assert await tile.locator(".ca-skillrun__check").count() == 1
        # #576: selection ring on image only (344×258); title outside below
        await pg.wait_for_timeout(400)  # #748 ring fades in over --ca-skillrun-select-dur
        ring = await tile.locator(".ca-skillrun__presetimg").evaluate(
            "el => { const a = getComputedStyle(el, '::after'); const r = el.getBoundingClientRect();"
            " return [a.boxShadow, Math.round(r.width), Math.round(r.height)] }")
        assert "1px" in ring[0] and ring[1:] == [344, 258]
        btn_shadow = await tile.get_by_test_id("skill-run-preset").evaluate(
            "el => getComputedStyle(el, '::after').boxShadow")
        assert btn_shadow in ("none", "")
        btn_h = (await tile.get_by_test_id("skill-run-preset").evaluate(BOX))[1]
        assert btn_h == 288  # image 258 + gap 8 + title 22

        assert await pg.get_by_test_id("skill-run-go").get_attribute("data-missing") == "1"  # productImage required, empty (#687: validated on click)
        await browser.close()


STAGE = """() => { const st = document.querySelector('[data-testid=skill-run-example-stage]'), i = st.querySelector('img');
  const a = st.getBoundingClientRect(), c = i.getBoundingClientRect(), cs = getComputedStyle(i);
  return {fit: cs.objectFit, pos: cs.objectPosition, bg: getComputedStyle(st).backgroundColor,
          st: [a.x, a.y, a.width, a.height], img: [c.x, c.y, c.width, c.height], nat: [i.naturalWidth, i.naturalHeight]} }"""


@pytest.mark.parametrize("skill,portrait", [("poster-differentiated-compiler", True), ("rednote-cover-maker", True), ("interior-architectural-visualization", True)])  # #569: character examples removed; #748: cover-design-director raw = 1 video (no still stage)
async def test_example_stage_contain_no_crop(app_url, skill, portrait):  # noqa: F811
    """Lovart stage: whole image visible (contain), centered, on #f4f4f4 - portrait must not overflow/crop."""
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh", "light")
        await _modal(pg, skill)
        if skill in ("cover-design-director", "banner-design-director"):  # #575 lead example is the wash mp4 → select the first still
            await pg.locator('[data-testid="skill-run-example-thumb"][data-media="image"]').first.click()
        await pg.wait_for_function("() => { const i = document.querySelector('[data-testid=skill-run-example-stage] img');"
                                   " return i && i.complete && i.naturalWidth > 0 }", timeout=60000)
        r = await pg.evaluate(STAGE)
        assert r["fit"] == "contain" and r["pos"] == "50% 50%"
        assert r["bg"] == "rgb(244, 244, 244)"
        sx, sy, sw, sh = r["st"]
        assert [round(sw), round(sh)] == [704, 506]  # design-spec frame
        assert [round(v) for v in r["img"]] == [round(sx), round(sy), round(sw), round(sh)]  # img box == stage box
        nw, nh = r["nat"]
        assert (nh > nw) == portrait
        k = min(sw / nw, sh / nh)  # contain scale: painted content fits inside the stage
        cw, ch = nw * k, nh * k
        assert cw <= sw + 0.5 and ch <= sh + 0.5
        assert abs(ch - sh) < 1 if portrait else abs(cw - sw) < 1  # fills the limiting axis
        await browser.close()


async def test_custom_workflow_card_removed(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "en")
        assert await pg.locator('[data-skill="custom-workflow"]').count() == 0  # no Lovart card
        await browser.close()
