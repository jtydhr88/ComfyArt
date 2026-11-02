"""#557/#585 e2e (mock only, $0): in the normal canvas chat, while /bot/status (the provider list) is still pending, the
composer mode pill and reference button already show their loaded form, so nothing flashes.

#557: no cache → Loomi + icon-only reference from first paint.
#585: with last-agent cache → DeepSeek stays DeepSeek while status is held; agent without shortLabel never shows raw id.

A MutationObserver records every pill/reference state from first paint; all must equal the loaded state.
Set CHAT_557_SHOTS=/dir for 1280x800 PNGs (zh light + en dark, held-loading frame + loaded).
Set CHAT_585_SHOTS=/dir for #585 tip-pin agent-chip shots (loading + after-load, cache seeded DeepSeek)."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("CHAT_557_SHOTS")
SHOTS_585 = os.environ.get("CHAT_585_SHOTS")


def _crop_chip(path: Path) -> None:
    """#585 tip-pin: keep composer agent-chip region for PR embeds."""
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(path)
    w, h = im.size
    im.crop((0, int(h * 0.72), int(w * 0.32), h)).save(path)


RECORD = """(() => {
  window.__seen557 = []
  const read = () => {
    const m = document.querySelector('.ca-composer__mode')
    if (!m) return
    const r = document.querySelector('.ca-composer__foot .ca-refbtn')
    const s = JSON.stringify([m.innerText.trim(), r ? r.innerText.trim() : null])
    if (window.__seen557[window.__seen557.length - 1] !== s) window.__seen557.push(s)
  }
  new MutationObserver(read).observe(document, { subtree: true, childList: true, characterData: true, attributes: true })
})()"""

CACHE_KEY = "comfyart.lastAgentLabel"

@pytest.fixture()
def fake_deepseek(monkeypatch):
    """Make deepseek-harness available so status resolve lands on DeepSeek after the hold."""
    from ComfyArt.bot import get_provider
    from ComfyArt.bot.providers import ProviderStatus

    async def ok(*_a):
        return ProviderStatus(available=True, version="1.0.0", logged_in=True, detail="")

    monkeypatch.setattr(get_provider("deepseek-harness"), "probe", ok)
    async def models(*_a):
        return ["deepseek/deepseek-v4.1-flash-1017"]
    monkeypatch.setattr(get_provider("deepseek-harness"), "list_models", models)


@pytest.fixture()
def fake_claude(monkeypatch):
    """Make claude-code available (no SHORT_LABELS entry) for the raw-id guard case."""
    from ComfyArt.bot import get_provider
    from ComfyArt.bot.providers import ProviderStatus

    async def ok(*_a):
        return ProviderStatus(available=True, version="1.0.0", logged_in=True, detail="")

    monkeypatch.setattr(get_provider("claude-code"), "probe", ok)
    async def models(*_a):
        return ["claude-sonnet"]
    monkeypatch.setattr(get_provider("claude-code"), "list_models", models)



def _cache_js(entry: dict | None) -> str:
    if entry is None:
        return f"localStorage.removeItem('{CACHE_KEY}');"
    return f"localStorage.setItem('{CACHE_KEY}',{json.dumps(json.dumps(entry))});"


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_mode_pill_and_ref_never_flash(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
        await pg.add_init_script(
            f"localStorage.setItem('comfyart.lang','{lang}');"
            f"localStorage.setItem('comfyart.theme','{theme}');"
            + _cache_js(None)
        )
        await pg.goto(app_url)
        await pg.wait_for_timeout(1500)
        await pg.mouse.click(28, 83)  # home: new project → canvas with the normal chat
        await pg.locator(".ca-composer__mode").wait_for()
        url = pg.url

        release = asyncio.Event()
        held: list[str] = []

        async def hold(route):
            held.append(route.request.url)
            await release.wait()
            try:
                await route.continue_()
            except Exception:  # page/route already gone at teardown
                pass
        await pg.route("**/comfyart/bot/status*", hold)
        await pg.add_init_script(RECORD)
        await pg.goto(url)
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(800)
        assert held, "provider list request was not held"
        loading = await pg.evaluate("window.__seen557.slice()")
        if SHOTS:
            Path(SHOTS).mkdir(parents=True, exist_ok=True)
            # shots only: lift the boot loader overlay so the composer state underneath (asserted above) is visible
            await pg.add_style_tag(content=".lm-loader{display:none!important}")
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=str(Path(SHOTS) / f"557-loading-{lang}-{theme}.png"))
        release.set()
        await pg.wait_for_function("document.querySelector('.ca-composer__mode')?.dataset.agent")
        await pg.wait_for_timeout(1000)
        if SHOTS:
            await pg.screenshot(path=str(Path(SHOTS) / f"557-loaded-{lang}-{theme}.png"))
        seen = await pg.evaluate("window.__seen557.slice()")
        await browser.close()
    final = seen[-1]
    assert final == '["Loomi",""]', seen  # loaded: product label + icon-only reference button
    assert loading and all(s == final for s in loading), (loading, final)  # before load: identical, no 「Agent / 参考」
    assert all(s == final for s in seen), seen


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_cached_deepseek_while_status_held(app_url, fake_deepseek, lang, theme):  # noqa: F811
    """#585 case A: last resolved agent was DeepSeek → while /bot/status is held ~2.5s, every sample stays DeepSeek."""
    from conftest import write_settings
    write_settings(**{"bot-provider": "deepseek-harness"})

    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
        await pg.add_init_script(
            f"localStorage.setItem('comfyart.lang','{lang}');"
            f"localStorage.setItem('comfyart.theme','{theme}');"
            + _cache_js({"id": "deepseek-harness", "shortLabel": "DeepSeek"})
        )
        await pg.goto(app_url)
        await pg.wait_for_timeout(1200)
        await pg.mouse.click(28, 83)
        await pg.locator(".ca-composer__mode").wait_for()
        url = pg.url

        release = asyncio.Event()
        held: list[str] = []

        done = asyncio.Event()

        async def hold(route):
            held.append(route.request.url)
            await asyncio.sleep(2.5)  # product: hold ~2.5s
            release.set()
            try:
                await route.continue_()
            except Exception:
                pass
            finally:
                done.set()

        await pg.route("**/comfyart/bot/status*", hold)
        await pg.add_init_script(RECORD)
        await pg.goto(url)
        await pg.locator(".ca-composer__mode").wait_for()
        # sample across the hold window (before status resolves)
        await pg.wait_for_timeout(1200)
        assert held, "provider list request was not held"
        loading = await pg.evaluate("window.__seen557.slice()")
        if SHOTS_585:
            Path(SHOTS_585).mkdir(parents=True, exist_ok=True)
            await pg.add_style_tag(content=".lm-loader{display:none!important}")
            await pg.wait_for_timeout(200)
            shot = Path(SHOTS_585) / f"AFTER-agent-chip-loading-{lang}-{theme}.png"
            await pg.screenshot(path=str(shot))
            _crop_chip(shot)
        # wait until held /bot/status has continued, then settle
        await done.wait()
        await pg.wait_for_function(
            "() => document.querySelector('.ca-composer__mode')?.dataset.agent === 'deepseek-harness'",
            timeout=15000,
        )
        await pg.wait_for_timeout(800)
        if SHOTS_585:
            shot = Path(SHOTS_585) / f"AFTER-agent-chip-loaded-{lang}-{theme}.png"
            await pg.screenshot(path=str(shot))
            _crop_chip(shot)
        seen = await pg.evaluate("window.__seen557.slice()")
        await browser.close()

    # every sample (loading + loaded) must show DeepSeek, never Loomi flash / raw id
    assert loading, loading
    assert all("DeepSeek" in s for s in loading), loading
    assert all("Loomi" not in s for s in loading), loading
    assert all("deepseek-harness" not in s for s in seen), seen
    assert all("DeepSeek" in s for s in seen), seen
    assert seen[-1].startswith('["DeepSeek"'), seen


@pytest.mark.parametrize("lang,theme", [("zh", "light"), ("en", "dark")])
async def test_no_raw_id_when_shortlabel_missing(app_url, fake_claude, lang, theme):  # noqa: F811
    """#585 case B: agent without SHORT_LABELS entry (claude-code) → never show raw id in loading samples."""
    from conftest import write_settings
    write_settings(**{"bot-provider": "claude-code"})

    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
        # Seed cache with raw-id shortLabel to prove write/read sanitizes; also covers missing SHORT_LABELS path.
        await pg.add_init_script(
            f"localStorage.setItem('comfyart.lang','{lang}');"
            f"localStorage.setItem('comfyart.theme','{theme}');"
            + _cache_js({"id": "claude-code", "shortLabel": "claude-code"})
        )
        await pg.goto(app_url)
        await pg.wait_for_timeout(1200)
        await pg.mouse.click(28, 83)
        await pg.locator(".ca-composer__mode").wait_for()
        url = pg.url

        held: list[str] = []

        done = asyncio.Event()

        async def hold(route):
            held.append(route.request.url)
            await asyncio.sleep(2.5)
            try:
                await route.continue_()
            except Exception:
                pass
            finally:
                done.set()

        await pg.route("**/comfyart/bot/status*", hold)
        await pg.add_init_script(RECORD)
        await pg.goto(url)
        await pg.locator(".ca-composer__mode").wait_for()
        await pg.wait_for_timeout(1200)
        assert held, "provider list request was not held"
        loading = await pg.evaluate("window.__seen557.slice()")
        await done.wait()
        await pg.wait_for_function(
            "() => document.querySelector('.ca-composer__mode')?.dataset.agent === 'claude-code'",
            timeout=15000,
        )
        await pg.wait_for_timeout(600)
        seen = await pg.evaluate("window.__seen557.slice()")
        texts = await pg.evaluate(
            "() => window.__seen557.map(s => { try { return JSON.parse(s)[0] } catch { return s } })"
        )
        await browser.close()

    assert loading, loading
    # never raw id in any sample (loading or loaded)
    assert all("claude-code" not in t for t in texts), texts
    assert all(t and t != "claude-code" for t in texts), texts
    # safe display from id → "Claude Code" (or server label once loaded)
    assert any("Claude" in t for t in texts), texts
