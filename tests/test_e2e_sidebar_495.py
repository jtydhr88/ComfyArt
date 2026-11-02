"""#495 sidebar e2e: expanded ~160 + labels + recent (max 8) + collapse persist. Mock only, $0."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("SIDEBAR_495_SHOTS")


def _snap(name: str) -> dict:
    return {
        "document": {
            "store": {"document:document": {"id": "document:document", "typeName": "document", "name": name}},
            "schema": {},
        },
        "session": {},
    }


async def _seed(pg, names: list[str]) -> None:
    for i, name in enumerate(names):
        pid = f"s495{i:02d}"
        status = await pg.evaluate(
            """async ({pid, name, snap, pinned}) => {
              const r = await fetch(`/comfyart/projects/${pid}`, {
                method: 'PUT', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({snapshot: snap, name, covers: []}),
              });
              if (!r.ok) return r.status;
              if (pinned) {
                const p = await fetch(`/comfyart/projects/${pid}`, {
                  method: 'PATCH', headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({pinned: true}),
                });
                return p.status;
              }
              return r.status;
            }""",
            {"pid": pid, "name": name, "snap": _snap(name), "pinned": i == 0},
        )
        assert status == 200, (pid, status)


async def _open(p, app_url, lang, theme, *, collapsed=False):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"""localStorage.setItem('comfyart.lang','{lang}');
            localStorage.setItem('comfyart.theme','{theme}');
            localStorage.setItem('comfyart.rail.collapsed','{"1" if collapsed else "0"}');"""
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("account-rail").wait_for()
    await pg.get_by_test_id("rail-home").wait_for()
    return browser, pg


async def _shot(pg, name: str) -> None:
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(500)
    await pg.screenshot(path=f"{SHOTS}/{name}.png")


NAMES = [
    "置顶示例",
    "Untitled",
    "品牌视觉提案",
    "电商主图改版",
    "用户搜索数据可视化",
    "海报草稿 A",
    "社交媒体套图",
    "包装结构探索",
    "第九个应被截断",
]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_sidebar_expanded_labels_recent(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme, collapsed=False)
        await _seed(pg, NAMES)
        await pg.reload()
        await pg.get_by_test_id("rail-recent").wait_for()
        rail = pg.get_by_test_id("account-rail")
        assert await rail.get_attribute("data-expanded") == "true"
        box = await rail.bounding_box()
        assert box and box["width"] == 240  # #546 Lovart
        # labels visible when expanded
        home = pg.get_by_test_id("rail-home")
        assert await home.locator(".ca-rail__label").inner_text() != ""
        # #539 PR-A: Assets entry now shown (was gated); competitor slots absent
        assert await pg.get_by_test_id("rail-assets").count() == 1
        assert await pg.get_by_test_id("rail-schedules").count() == 1
        assert await pg.get_by_test_id("rail-ws-history").count() == 0  # #498: moved into SettingsMenu
        assert await pg.get_by_test_id("rail-settings").count() == 1
        rows = pg.get_by_test_id("rail-recent-row")
        assert await rows.count() == 8
        # ⋯ menu has 4 items
        await rows.first.hover()
        await pg.get_by_test_id("rail-recent-more").first.click()
        menu = pg.get_by_test_id("rail-recent-menu")
        await menu.wait_for()
        assert await menu.locator(".ca-menu__item").count() == 4
        await pg.keyboard.press("Escape")
        await _shot(pg, f"sidebar-expanded-{lang}-{theme}")
        # collapse → icon rail, no recent
        await pg.get_by_test_id("rail-collapse").click()
        assert await rail.get_attribute("data-collapsed") == "true"
        assert await pg.get_by_test_id("rail-recent").count() == 0
        box2 = await rail.bounding_box()
        assert box2 and box2["width"] <= 70
        assert await pg.evaluate("() => localStorage.getItem('comfyart.rail.collapsed')") == "1"
        await _shot(pg, f"sidebar-collapsed-{lang}-{theme}")
        # expand via logo
        await pg.get_by_test_id("rail-expand").click()
        await pg.get_by_test_id("rail-recent").wait_for()
        assert await pg.evaluate("() => localStorage.getItem('comfyart.rail.collapsed')") == "0"
        await browser.close()


async def test_sidebar_empty_hides_recent(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh", "light", collapsed=False)
        await pg.get_by_test_id("rail-home").wait_for()
        assert await pg.get_by_test_id("rail-recent").count() == 0
        await browser.close()


ASSET_SHOTS = os.environ.get("ASSETS_539_SHOTS")


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_assets_page_shell_539(app_url, lang, theme):  # noqa: F811
    """#539 PR-A: rail → Assets page; 4 kit tabs (no 文件); empty state; no demo data."""
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
        pg = await ctx.new_page()
        await pg.add_init_script(
            f"""localStorage.setItem('comfyart.lang','{lang}');
                localStorage.setItem('comfyart.theme','{theme}');
                localStorage.setItem('comfyart.rail.collapsed','1');"""
        )
        await pg.goto(app_url)
        await pg.get_by_test_id("rail-assets").wait_for()
        if ASSET_SHOTS:
            Path(ASSET_SHOTS).mkdir(parents=True, exist_ok=True)
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539a-entry-{lang}-{theme}.png")
        await pg.get_by_test_id("rail-assets").click()
        await pg.get_by_test_id("assets-page").wait_for()
        assert "view=assets" in pg.url
        assert await pg.get_by_test_id("rail-assets").get_attribute("data-on") == "true"
        tabs = pg.get_by_test_id("assets-library").get_by_role("tab")
        assert await tabs.count() == 4
        want = ["品牌套件", "角色", "产品", "自定义"] if lang == "zh" else None
        names = [await tabs.nth(i).inner_text() for i in range(4)]
        if want:
            assert names == want, names
        assert "文件" not in names and "Files" not in names
        await pg.get_by_test_id("assets-detail-empty").wait_for()
        # no demo data: fresh library → zero cards in every tab
        for i in range(4):
            await tabs.nth(i).click()
            assert await pg.locator(".ca-lib__card").count() == 0
            # #539 PR-B: assertion updated (not removed) — kitsOnly list keeps only 新建; the hint
            # moved to the right-pane empty state (one line + 新建, no icon, no auto-created kit).
            assert await pg.locator(".ca-side__empty").count() == 0
            await pg.get_by_test_id("assets-detail-empty").wait_for()
            assert await pg.get_by_test_id("assets-empty-new").count() == 1
            assert await pg.locator(".ca-assets-page__right .ca-icon").count() == 0
        await tabs.nth(0).click()
        if ASSET_SHOTS:
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539a-empty-{lang}-{theme}.png")
        await browser.close()


async def tabs_new_unselected(pg, style, sel):
    """create a 2nd kit → it becomes selected; the first (now unselected) must not keep the selected style."""
    await pg.get_by_test_id("assets-new").click()
    await pg.wait_for_timeout(300)
    cards = pg.locator(".ca-lib__card")
    assert await cards.count() == 2
    assert await pg.locator(".ca-lib__card[data-on]").count() == 1
    await pg.mouse.move(1200, 780)
    off = pg.locator(".ca-lib__card:not([data-on])")
    assert await off.evaluate(style) != sel
    # delete the 2nd kit via the title 「…」, un-hovered (P1 2) → selection falls back to the first kit
    assert await pg.get_by_test_id("assets-detail-more").evaluate("e => getComputedStyle(e).opacity") == "1"
    await pg.get_by_test_id("assets-detail-more").click()
    await pg.locator(".ca-lib__menu .ca-menu__item--danger").click()
    await pg.locator(".ca-confirm .ca-panel__primary").click()
    await pg.wait_for_timeout(500)
    assert await cards.count() == 1
    await pg.mouse.move(1200, 780)
    await pg.wait_for_timeout(300)
    assert await pg.locator(".ca-lib__card[data-on]").evaluate(style) == sel


async def _assets_page(p, lang, theme):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800})
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"""localStorage.setItem('comfyart.lang','{lang}');
            localStorage.setItem('comfyart.theme','{theme}');
            localStorage.setItem('comfyart.rail.collapsed','1');"""
    )
    return browser, pg


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_assets_detail_539b(app_url, lang, theme):  # noqa: F811
    """#539 PR-B / #632: list 380@1280 / dashed 新建; empty state; create → default-select → rename → reload persists."""
    async with pw.async_playwright() as p:
        browser, pg = await _assets_page(p, lang, theme)
        await pg.goto(app_url + "?view=assets")
        await pg.get_by_test_id("assets-page").wait_for()
        left = await pg.locator(".ca-assets-page__left").bounding_box()
        assert abs(round(left["width"]) - 380) <= 8, left  # #632: fixed 380px (±8); void 12.5vw crush
        new = pg.get_by_test_id("assets-new")
        assert await new.evaluate("e => getComputedStyle(e).borderTopStyle") == "dashed"
        assert await pg.locator(".ca-assets-page__title").evaluate("e => getComputedStyle(e).fontSize") == "15px"
        # empty: no auto-created kit
        await pg.get_by_test_id("assets-detail-empty").wait_for()
        await pg.wait_for_timeout(600)
        assert await pg.locator(".ca-lib__card").count() == 0
        if ASSET_SHOTS:
            await pg.screenshot(path=f"{ASSET_SHOTS}/539b-empty-{lang}-{theme}.png")
        # create via the empty-state 新建 (same action as list 新建) → selected in detail
        await pg.get_by_test_id("assets-empty-new").click()
        await pg.get_by_test_id("assets-detail").wait_for()
        assert await pg.locator(".ca-lib__card").count() == 1
        page = await pg.locator(".ca-kit[data-embedded] .ca-kit__page").bounding_box()
        assert round(page["width"]) == 800, page
        foot = await pg.get_by_test_id("assets-detail-foot").bounding_box()
        detail = await pg.locator(".ca-assets-page__detail").bounding_box()
        assert round(foot["width"]) == round(detail["width"])
        # #539 PR-C: CTA now wired — click/landing covered by test_assets_c_539
        await pg.get_by_test_id("assets-create-project").wait_for()
        await pg.get_by_test_id("assets-import-url").wait_for()
        # rename persists across reload; then back to the default 新建 name (design P2 #4: no custom names in shots)
        name = "示例" if lang == "zh" else "Sample"
        await pg.get_by_test_id("assets-detail-name").fill(name)
        await pg.get_by_test_id("assets-detail-name").press("Enter")
        await pg.wait_for_timeout(800)
        await pg.reload()
        await pg.get_by_test_id("assets-detail").wait_for()
        assert await pg.get_by_test_id("assets-detail-name").input_value() == name
        await pg.get_by_test_id("assets-detail-name").fill("")
        await pg.get_by_test_id("assets-detail-name").press("Enter")
        await pg.wait_for_timeout(800)
        # reload → persisted + default-selected first kit
        await pg.reload()
        await pg.get_by_test_id("assets-detail").wait_for()
        # P1 1: cleared name falls back to the card's default name, in body colour
        title = pg.get_by_test_id("assets-detail-name")
        card_name = (await pg.locator(".ca-lib__card[data-on] .ca-lib__name").inner_text()).strip()
        assert await title.input_value() == card_name == ("未命名" if lang == "zh" else "Untitled")  # #497 short default
        colors = await title.evaluate("e => [getComputedStyle(e).color, getComputedStyle(e, '::placeholder').color, getComputedStyle(document.body).color]")
        assert colors[0] == colors[2] and colors[0] != colors[1], colors
        # P1 2: title 「…」 visible without hover
        await pg.mouse.move(1200, 780)
        await pg.wait_for_timeout(300)
        assert await pg.get_by_test_id("assets-detail-more").evaluate("e => getComputedStyle(e).opacity") == "1"
        assert await pg.get_by_test_id("assets-detail-more").is_visible()
        assert await pg.locator(".ca-lib__card[data-on]").count() == 1
        if ASSET_SHOTS:
            await pg.mouse.move(0, 0)
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539b-selected-{lang}-{theme}.png")
        # product ruling: list + empty create button read 新建 / New on every tab
        assert (await pg.get_by_test_id("assets-new").inner_text()).strip().lstrip("+").strip() == ("新建" if lang == "zh" else "New")
        # persistent selected style, distinct from unselected, survives mouse-out
        style = "e => { const s = getComputedStyle(e); return [s.backgroundColor, s.borderTopColor] }"
        on = pg.locator(".ca-lib__card[data-on]")
        await on.hover()
        await pg.mouse.move(1200, 780)
        await pg.wait_for_timeout(300)
        sel = await on.evaluate(style)
        want = ["rgb(245, 245, 245)", "rgb(228, 228, 228)"] if theme == "light" else ["rgb(38, 38, 38)", "rgb(54, 54, 54)"]
        assert sel == want, sel
        await tabs_new_unselected(pg, style, sel)
        # other tab with no kits → empty state; back → selected again
        tabs = pg.get_by_test_id("assets-library").get_by_role("tab")
        await tabs.nth(1).click()
        await pg.get_by_test_id("assets-detail-empty").wait_for()
        await tabs.nth(0).click()
        await pg.get_by_test_id("assets-detail").wait_for()
        # delete via 「…」 → empty, persisted after reload
        await pg.get_by_test_id("assets-detail-more").click()
        await pg.locator(".ca-lib__menu .ca-menu__item--danger").click()
        await pg.locator(".ca-confirm .ca-panel__primary").click()
        await pg.get_by_test_id("assets-detail-empty").wait_for()
        await pg.wait_for_timeout(500)
        await pg.reload()
        await pg.get_by_test_id("assets-detail-empty").wait_for()
        assert await pg.locator(".ca-lib__card").count() == 0
        await browser.close()


async def test_canvas_library_unchanged_539b(app_url):  # noqa: F811
    """#539 PR-B no-regression: canvas LibraryPanel keeps 5 tabs (incl. 文件) + solid 新建; KitEditor stays the overlay."""
    async with pw.async_playwright() as p:
        browser, pg = await _assets_page(p, "zh", "light")
        await pg.goto(app_url)
        await pg.get_by_test_id("rail-new").click()
        await pg.locator(".tl-canvas").wait_for()
        await pg.wait_for_timeout(1500)
        if await pg.locator(".ca-modal").count():
            await pg.locator(".ca-modal button").nth(-2).click()
        await pg.locator('button[title="我的素材"]').first.click()
        lib = pg.locator(".ca-lib").first
        await lib.wait_for()
        assert await pg.get_by_test_id("assets-library").count() == 0
        tabs = lib.get_by_role("tab")
        assert await tabs.count() == 5
        assert "文件" in [await tabs.nth(i).inner_text() for i in range(5)]
        await tabs.nth(1).click()
        new = lib.locator(".ca-lib__new")
        assert await new.evaluate("e => getComputedStyle(e).borderTopStyle") == "solid"
        assert await lib.locator(".ca-side__empty").count() == 1
        await new.click()
        kit = pg.locator(".ca-kit")
        await kit.wait_for()
        assert await kit.get_attribute("data-embedded") is None
        assert await kit.evaluate("e => getComputedStyle(e).position") == "fixed"
        assert await pg.locator(".ca-kit__bar").count() == 1
        if ASSET_SHOTS:
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539b-canvas-kiteditor-zh-light.png")
        await pg.locator(".ca-kit__title").focus()
        await pg.keyboard.press("Escape")  # canvas overlay still closes on Escape
        await pg.wait_for_timeout(300)
        assert await pg.locator(".ca-kit").count() == 0
        assert await lib.locator(".ca-lib__card").count() == 1
        if ASSET_SHOTS:
            await pg.screenshot(path=f"{ASSET_SHOTS}/539b-canvas-library-zh-light.png")
        await browser.close()


_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c63f8cfc0f01f0005000201a1d5b5e10000000049454e44ae426082"
)


async def _right_edges(pg):
    cta = await pg.get_by_test_id("assets-create-project").bounding_box()
    page = await pg.locator(".ca-kit[data-embedded] .ca-kit__page").bounding_box()
    return cta["x"] + cta["width"], page["x"] + page["width"]


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_assets_c_539(app_url, lang, theme):  # noqa: F811
    """#539 PR-C: arrow zone w/o dashed border, single-line guide, hover-only 「…」, 20MB error,
    URL import (mocked image host), CTA aligned to 800 content (1280 + 1920), CTA → new project with kit."""
    async with pw.async_playwright() as p:
        browser, pg = await _assets_page(p, lang, theme)
        await pg.route("https://img.example.com/**", lambda r: r.fulfill(status=200, headers={"access-control-allow-origin": "*"}, content_type="image/webp" if r.request.url.endswith(".webp") else "application/pdf" if "download" in r.request.url else "image/png", body=_PNG))
        await pg.goto(app_url + "?view=assets")
        await pg.get_by_test_id("assets-detail-empty").wait_for()
        await pg.get_by_test_id("assets-empty-new").click()  # default-name flow, no custom name
        await pg.get_by_test_id("assets-detail").wait_for()
        drop = pg.locator(".ca-kit[data-embedded] .ca-kit__drop")
        assert await drop.evaluate("e => getComputedStyle(e).borderTopStyle") == "none"
        assert await drop.locator(".ca-icon path").count() == 3  # uploadArrow, not the paperclip
        guide = pg.get_by_test_id("assets-guide")
        h = (await guide.bounding_box())["height"]
        assert 28 <= h <= 32, h
        # 「…」 hidden until hover on the card only; title 「…」 always shown
        card = pg.locator(".ca-assets-page .ca-lib__card").first
        await pg.mouse.move(1200, 780)
        await pg.wait_for_timeout(300)
        assert await pg.get_by_test_id("assets-detail-more").evaluate("e => getComputedStyle(e).opacity") == "1"
        assert await card.locator(".ca-lib__more").evaluate("e => getComputedStyle(e).opacity") == "0"
        await card.hover()
        await pg.wait_for_timeout(300)
        assert await card.locator(".ca-lib__more").evaluate("e => getComputedStyle(e).opacity") == "1"
        await pg.mouse.move(1200, 780)
        # P2 5: CTA right edge = 800 content right edge
        cta_r, page_r = await _right_edges(pg)
        assert abs(cta_r - page_r) <= 1, (cta_r, page_r)
        if ASSET_SHOTS:
            await pg.wait_for_timeout(400)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539c-detail-{lang}-{theme}.png")
        # (a) 21MB file rejected with i18n error, nothing added
        await pg.locator(".ca-kit[data-embedded] input[type=file][multiple]").first.set_input_files(
            {"name": "big.png", "mimeType": "image/png", "buffer": b"\0" * (21 * 1024 * 1024)}
        )
        err = pg.get_by_test_id("assets-upload-error")
        await err.wait_for()
        text = await err.inner_text()
        assert ("文件超过 20MB" if lang == "zh" else "File exceeds 20MB") in text and "big.png" in text
        assert await pg.locator(".ca-mem-toast").count() == 0  # P2: inline only, no toast
        assert await pg.locator(".ca-kit[data-embedded] .ca-kit__tiles img").count() == 0
        if ASSET_SHOTS:
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539c-20mb-{lang}-{theme}.png")
        # bad local format → error, nothing written
        await pg.locator(".ca-kit[data-embedded] input[type=file][multiple]").first.set_input_files(
            {"name": "anim.gif", "mimeType": "image/gif", "buffer": _PNG}
        )
        await pg.wait_for_timeout(300)
        assert ("仅支持 PNG、JPG、PDF" if lang == "zh" else "Only PNG, JPG and PDF") in await err.inner_text()
        assert await pg.locator(".ca-kit[data-embedded] .ca-kit__tiles img").count() == 0
        assert await pg.locator(".ca-mem-toast").count() == 0  # P2: inline only, no toast over 我的素材
        if ASSET_SHOTS and lang == "zh":
            await pg.screenshot(path=f"{ASSET_SHOTS}/539c-badformat-p2-zh-light.png")
        # (b) URL import: invalid → i18n error; https → reference tile
        await pg.get_by_test_id("assets-import-url").click()
        assert await err.count() == 0  # P2: opening the URL row clears the stale upload error
        # P2 design spec for 「添加」: 32 high, r8, px12, 13/20, theme colours, disabled+0.4 when empty, gap 8
        save, cancel, inp = pg.get_by_test_id("assets-url-save"), pg.get_by_test_id("assets-url-cancel"), pg.get_by_test_id("assets-url-input")
        spec = "e => { const s = getComputedStyle(e); return [s.height, s.borderTopLeftRadius, s.paddingLeft, s.paddingRight, s.fontSize, s.lineHeight, s.backgroundColor, s.color, s.opacity] }"
        bg, fg = ("rgb(25, 25, 25)", "rgb(255, 255, 255)") if theme == "light" else ("rgb(232, 232, 232)", "rgb(22, 22, 22)")
        assert await save.evaluate(spec) == ["32px", "8px", "12px", "12px", "13px", "20px", bg, fg, "0.4"]
        assert await save.is_disabled()
        assert (await cancel.bounding_box())["height"] == 32 and (await inp.bounding_box())["height"] == 32
        if ASSET_SHOTS:
            await inp.fill("https://img.example.com/ref.png")
            await pg.wait_for_timeout(200)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539c-url-row-p2-{lang}-{theme}.png")
            await inp.fill("")
        await inp.fill("https://x.example.com/a.png")
        assert not await save.is_disabled() and await save.evaluate("e => getComputedStyle(e).opacity") == "1"
        sb, cb = await save.bounding_box(), await cancel.bounding_box()
        assert round(cb["x"] - (sb["x"] + sb["width"])) == 8
        await pg.get_by_test_id("assets-url-input").fill("ftp://x")
        await pg.get_by_test_id("assets-url-save").click()
        uerr = await pg.get_by_test_id("assets-url-error").inner_text()
        assert uerr == ("请输入有效的 http 或 https URL" if lang == "zh" else "Enter a valid http or https URL")
        # neither extension nor content-type confirms → error, text kept, nothing written, no dialog
        bad = "https://img.example.com/pic.webp"
        await pg.get_by_test_id("assets-url-input").fill(bad)
        await pg.get_by_test_id("assets-url-save").click()
        uerr = pg.get_by_test_id("assets-url-error")
        await pg.wait_for_timeout(500)
        assert (await uerr.inner_text()) == ("无法确认链接是 PNG、JPG 或 PDF" if lang == "zh" else "Couldn't confirm the link is a PNG, JPG or PDF")
        assert await pg.get_by_test_id("assets-url-input").input_value() == bad
        assert await pg.locator(".ca-kit[data-embedded] .ca-kit__tiles img").count() == 0
        assert await pg.locator(".ca-confirm").count() == 0
        assert await err.count() == 0 and await pg.locator(".ca-mem-toast").count() == 0
        if ASSET_SHOTS and lang == "zh":
            await pg.screenshot(path=f"{ASSET_SHOTS}/539c-urlformat-p2-zh-light.png")
        # P2: stale-error case — gif badFormat, then a bad .webp URL → only urlFormat, no toast
        await pg.get_by_test_id("assets-url-cancel").click()
        assert await pg.get_by_test_id("assets-url-error").count() == 0
        await pg.locator(".ca-kit[data-embedded] input[type=file][multiple]").first.set_input_files(
            {"name": "anim.gif", "mimeType": "image/gif", "buffer": _PNG}
        )
        await err.wait_for()
        await pg.get_by_test_id("assets-import-url").click()
        await pg.get_by_test_id("assets-url-input").fill(bad)
        await pg.get_by_test_id("assets-url-save").click()
        await pg.wait_for_timeout(500)
        assert (await uerr.inner_text()) == ("无法确认链接是 PNG、JPG 或 PDF" if lang == "zh" else "Couldn't confirm the link is a PNG, JPG or PDF")
        assert await err.count() == 0
        assert await pg.locator(".ca-mem-toast").count() == 0
        assert await pg.locator(".ca-kit[data-embedded] .ca-kit__tiles img").count() == 0
        await pg.get_by_test_id("assets-url-input").fill("https://img.example.com/ref.png")
        if ASSET_SHOTS:
            await pg.screenshot(path=f"{ASSET_SHOTS}/539c-url-input-{lang}-{theme}.png")
        await pg.get_by_test_id("assets-url-save").click()
        await pg.locator('.ca-kit[data-embedded] .ca-kit__tiles img[src="https://img.example.com/ref.png"]').wait_for()
        assert await pg.get_by_test_id("assets-url-row").count() == 0
        if ASSET_SHOTS:
            await pg.wait_for_timeout(500)
            await pg.screenshot(path=f"{ASSET_SHOTS}/539c-url-imported-{lang}-{theme}.png")
        # PDF passes by extension, and by application/pdf content-type without one
        tiles = pg.locator(".ca-kit[data-embedded] .ca-kit__tiles img")
        for i, u in enumerate(["https://img.example.com/doc.pdf", "https://img.example.com/download?id=7"]):
            await pg.get_by_test_id("assets-import-url").click()
            await pg.get_by_test_id("assets-url-input").fill(u)
            await pg.get_by_test_id("assets-url-save").click()
            await pg.locator(f'.ca-kit[data-embedded] .ca-kit__tiles img[src="{u}"]').wait_for(state="attached")
            assert await pg.get_by_test_id("assets-url-row").count() == 0
            assert await tiles.count() == 2 + i
        # wide viewport: still aligned
        await pg.set_viewport_size({"width": 1920, "height": 1080})
        await pg.wait_for_timeout(300)
        cta_r, page_r = await _right_edges(pg)
        assert abs(cta_r - page_r) <= 1, (cta_r, page_r)
        await pg.set_viewport_size({"width": 1280, "height": 800})
        await pg.wait_for_timeout(1000)  # let the debounced save land
        # (c) CTA → new project carrying the selected kit
        seen: list[str] = []
        pg.on("framenavigated", lambda f: seen.append(f.url) if f == pg.main_frame else None)
        async with pg.expect_navigation():
            await pg.get_by_test_id("assets-create-project").click()
        assert "project=" in pg.url
        await pg.locator(".tl-canvas").wait_for()
        await pg.wait_for_timeout(1500)
        assert any("kit=" in u for u in seen), seen
        assert "kit=" not in pg.url  # consumed by the project as its brand kit
        if ASSET_SHOTS:
            await pg.screenshot(path=f"{ASSET_SHOTS}/539c-new-project-{lang}-{theme}.png")
        await browser.close()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_assets_c_kinds_539(app_url, lang, theme):  # noqa: F811
    """#539 PR-C: 「使用此素材创建项目 →」 on all 4 tabs opens a new project carrying that kit; nothing auto-sent."""
    async with pw.async_playwright() as p:
        browser, pg = await _assets_page(p, lang, theme)
        for i, kind in enumerate(["brand", "character", "product", "custom"]):
            await pg.goto(app_url + "?view=assets")
            await pg.get_by_test_id("assets-page").wait_for()
            await pg.get_by_test_id("assets-library").get_by_role("tab").nth(i).click()
            await pg.get_by_test_id("assets-detail-empty").wait_for()
            await pg.get_by_test_id("assets-empty-new").click()
            await pg.get_by_test_id("assets-detail").wait_for()
            await pg.wait_for_timeout(800)
            seen: list[str] = []
            pg.on("framenavigated", lambda f: seen.append(f.url) if f == pg.main_frame else None)
            async with pg.expect_navigation():
                await pg.get_by_test_id("assets-create-project").click()
            await pg.locator(".tl-canvas").wait_for()
            await pg.wait_for_timeout(1500)
            kit_id = next(u for u in seen if "kit=" in u).split("kit=")[1].split("&")[0]
            brand_kit = await pg.evaluate("() => window.__caEditor.getDocumentSettings().meta.brandKit")
            chips = pg.locator(".ca-composer__chips .ca-chip")
            if kind == "brand":
                assert brand_kit == kit_id, (brand_kit, kit_id)
                assert await chips.count() == 0
            else:
                assert brand_kit != kit_id
                assert await chips.count() == 1
                assert (await chips.first.inner_text()).strip()  # untitled kit label, not blank
            # nothing sent automatically: no user message in the chat
            assert await pg.get_by_test_id("chat-empty").count() == 1
            if kind == "character" and ASSET_SHOTS:
                await pg.screenshot(path=f"{ASSET_SHOTS}/539c-new-project-character-{lang}-{theme}.png")
        await browser.close()
