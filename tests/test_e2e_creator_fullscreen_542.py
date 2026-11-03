"""#542 e2e (mock only, $0): home + → 技能 → 创建技能 and the Skills page 「创建」 land in the same state —
chat-only full screen, 技能创建器 chip, caret in the input, nothing sent; landing has 3 stacked buttons;
选择 Skill inserts "/" and opens the skills list; collapsing keeps typed text with no confirm dialog.
Set CREATOR_542_SHOTS=/dir for 1280-wide top-anchored PNGs (zh light + en dark, both entries) + a click→landing frame sequence."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("CREATOR_542_SHOTS")


async def _page(p, app_url, lang, theme, path=""):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    sends: list[str] = []
    pg.on("request", lambda r: sends.append(r.url) if r.method == "POST" and "/bot" in r.url and "send" in r.url else None)
    dialogs: list[str] = []
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    await pg.goto(app_url.rstrip("/") + path)
    return browser, pg, sends, dialogs


async def _via_home(pg, frames: str | None = None):
    await pg.get_by_test_id("home-plus").click()
    await pg.get_by_test_id("home-plus-skills").click()
    await pg.get_by_test_id("home-skills-more").click()
    await pg.get_by_test_id("home-create-skill").click()


async def _via_skills(pg, frames: str | None = None):
    await pg.get_by_test_id("skills-create").click()


async def _landing_state(pg) -> dict:
    await pg.get_by_test_id("creator-landing-title").wait_for()
    await pg.wait_for_function("document.activeElement?.classList.contains('ca-composer__input')")
    return await pg.evaluate("""() => ({
      max: !!document.querySelector('.ca-agent[data-max]'),
      chip: document.querySelector('[data-testid="skill-creator-chip"]')?.textContent?.trim(),
      focus: document.activeElement?.className,
      draft: document.querySelector('.ca-composer__input').value,
      placeholder: document.querySelector('.ca-composer__input').placeholder,
      bubbles: document.querySelectorAll('[data-testid="user-bubble"]').length,
      buttons: [...document.querySelectorAll('[data-creator] .ca-chat__start')].map(b => {
        const r = b.getBoundingClientRect(); if (b.scrollWidth > b.clientWidth + 1 || b.querySelectorAll('*').length && [...b.childNodes].some(n => n.nodeType === 3 && n.parentElement && (() => { const g = document.createRange(); g.selectNodeContents(n); return g.getClientRects().length > 1 })())) return ['wrap']; return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] }),
      newProject: !!new URL(location.href).searchParams.get('project'),
      mode: document.querySelector('.ca-composer__mode').innerText.trim(),
      modeAgent: document.querySelector('.ca-composer__mode').dataset.agent || null,
      ref: document.querySelector('.ca-refbtn')?.innerText.trim() ?? null,
      top: (() => { const r = [...document.querySelectorAll('.ca-agent .ca-head .ca-bar__btn')].map(b => b.getBoundingClientRect()).filter(r => r.width);
        return [Math.round(innerWidth - Math.max(...r.map(x => x.right))), Math.round(Math.min(...r.map(x => x.left)))] })(),
    })""")


async def _shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"), clip={"x": 0, "y": 0, "width": 1280, "height": 800})


@pytest.mark.parametrize("lang,theme,chip", [("zh", "light", "技能创建器"), ("en", "dark", "Skill Creator")])
async def test_both_entries_identical(app_url, lang, theme, chip):  # noqa: F811
    states = {}
    async with pw.async_playwright() as p:
        for name, path, go in (("home", "", _via_home), ("skills", "/?view=skills", _via_skills)):
            browser, pg, sends, dialogs = await _page(p, app_url, lang, theme, path)
            await go(pg)
            s = await _landing_state(pg)
            await pg.wait_for_timeout(800)  # anything auto-sent would have gone out by now
            s["bubbles"] = await pg.locator('[data-testid="user-bubble"]').count()
            assert not sends and not dialogs, (sends, dialogs)
            await _shot(pg, f"542-{name}-{lang}-{theme}")
            states[name] = s
            await browser.close()
    h, k = states["home"], states["skills"]
    assert h == k, (h, k)
    assert h["max"] and h["chip"] == chip and "ca-composer__input" in h["focus"] and h["draft"] == "" and h["bubbles"] == 0
    assert h["newProject"] is True  # (4) entering creates a new canvas project
    # P1-1: both entries show the normal composer's product label (Loomi, never the 'Agent' fallback) in zh and en,
    # and the reference control is main's normal-composer form (icon only next to a product pill)
    assert h["mode"] == "Loomi" and h["modeAgent"], h
    assert h["ref"] == "", h
    # P1-2: the full-screen top-bar group (saved / new chat / notices / expand / collapse) sits at the top right
    assert h["top"][0] <= 24 and h["top"][1] > 640, h["top"]
    assert h["placeholder"] == ""  # #650: gold creator input is empty
    # 3 buttons, stacked, centred, ~172x38, not stretched
    b = h["buttons"]
    assert len(b) == 3 and all(w == 172 and ht == 38 for _, _, w, ht in b)
    assert len({x for x, _, _, _ in b}) == 1 and abs((b[0][0] + 86) - 640) <= 2
    assert b[1][1] - b[0][1] == b[2][1] - b[1][1] == 38 + 15


async def test_frames_click_to_landing(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg, *_ = await _page(p, app_url, "zh", "light", "/?view=skills")
        await pg.get_by_test_id("skills-create").wait_for()
        await _shot(pg, "542-frames-0-skills")
        await pg.get_by_test_id("skills-create").hover()
        await _shot(pg, "542-frames-1-hover")
        await pg.get_by_test_id("skills-create").click()
        await pg.locator(".ca-agent").wait_for()
        if SHOTS:
            await pg.screenshot(path=str(Path(SHOTS) / "542-frames-2-loading.png"), clip={"x": 0, "y": 0, "width": 1280, "height": 800})
        await _landing_state(pg)
        await _shot(pg, "542-frames-3-landing")
        await browser.close()


async def test_pick_skill_inserts_slash_and_opens_list(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg, sends, _ = await _page(p, app_url, "zh", "light", "/?view=skills")
        await _via_skills(pg)
        await _landing_state(pg)
        await pg.locator("[data-creator] .ca-chat__start").nth(1).click()
        assert await pg.locator(".ca-composer__input").input_value() == "/"
        await pg.locator(".ca-composer .ca-menu").first.wait_for()  # existing skills list
        assert await pg.locator(".ca-composer .ca-menu .ca-menu__item").count() > 0
        assert not sends
        await browser.close()


async def test_collapse_keeps_text_without_confirm(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg, sends, dialogs = await _page(p, app_url, "zh", "light", "/?view=skills")
        await _via_skills(pg)
        await _landing_state(pg)
        await pg.locator(".ca-composer__input").fill("做一个海报技能")
        await pg.get_by_title("收起对话区").click()
        await pg.locator(".ca-agent").wait_for(state="detached")
        await pg.get_by_title("展开对话区").click()
        assert await pg.locator(".ca-composer__input").input_value() == "做一个海报技能"
        await pg.go_back()
        await pg.wait_for_timeout(500)
        assert not dialogs and not sends
        await browser.close()


async def test_brand_kit_leaves_full_screen_and_keeps_text(app_url):  # noqa: F811
    """#542 product ruling: 使用品牌套件 switches back to normal view; the typed text stays; nothing is sent."""
    async with pw.async_playwright() as p:
        browser, pg, sends, dialogs = await _page(p, app_url, "zh", "light", "/?view=skills")
        await _via_skills(pg)
        await _landing_state(pg)
        await pg.locator(".ca-composer__input").fill("做一个咖啡店海报技能")
        await pg.locator("[data-creator] .ca-chat__start").nth(2).click()
        await pg.locator(".ca-agent[data-max]").wait_for(state="detached")
        assert await pg.locator(".ca-agent").count() == 1  # normal (docked) chat view
        await pg.locator(".ca-lib").wait_for()
        assert (await pg.locator('.ca-lib [role="tab"][aria-selected="true"]').inner_text()).strip() == "品牌套件"
        assert await pg.locator(".ca-composer__input").input_value() == "做一个咖啡店海报技能"
        assert await pg.locator('[data-testid="skill-creator-chip"]').count() == 1
        await pg.wait_for_timeout(500)
        assert not sends and not dialogs
        await browser.close()


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_normal_full_screen_chat_composer(app_url, lang, theme):  # noqa: F811
    """#542: every full-screen chat (not only the creator) uses the 720-wide input card docked 8px from the bottom."""
    async with pw.async_playwright() as p:
        browser, pg, sends, _ = await _page(p, app_url, lang, theme, "/?project=n542abcd&new=1")
        await pg.locator(".ca-composer__input").wait_for()
        await pg.locator(".ca-agent .ca-wide-only").click()
        await pg.locator(".ca-agent[data-max]").wait_for()
        await pg.mouse.move(1, 400)
        await _shot(pg, f"542-normal-max-{lang}-{theme}")
        box = await pg.locator(".ca-agent .ca-composer").bounding_box()
        assert await pg.locator('[data-testid="creator-landing-title"]').count() == 0
        assert round(box["width"]) == 720 and abs(box["x"] + 360 - 640) <= 2
        assert abs(800 - (box["y"] + box["height"]) - 8) <= 1
        assert not sends
        await browser.close()
