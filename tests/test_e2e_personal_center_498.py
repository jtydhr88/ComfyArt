"""#498 e2e: capture #78 AFTER shots for personal SettingsMenu + Usage modal.

Set SHOT_OUT=<dir> (default docs/design/498/78/after) to save PNGs.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools, pytestmark  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("SHOT_OUT", str(ROOT / "docs/design/498/78/after")))


async def _shot(pg, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    await pg.screenshot(path=str(OUT / f"{name}.png"), full_page=False)


async def _open(p, app_url, lang: str, theme: str):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        "localStorage.setItem('comfyart.rail.collapsed','0');"
        "localStorage.setItem('comfyart.e2e','1');"
        "window.__opened=[];"
        "window.open=function(url){window.__opened.push(String(url));return null};"
    )
    await pg.goto(app_url.rstrip("/") + "/")
    return browser, pg


@pytest.mark.asyncio
async def test_78_shots_zh_light_menu_usage_submenus(app_url, fake_tools, monkeypatch, mock_ws):  # noqa: F811
    from ComfyArt.api import wavespeed
    async def _bal(key): return 12.34
    monkeypatch.setattr(wavespeed, "fetch_balance", _bal)
    # seed a couple usage rows via store
    from ComfyArt.api.providers import ensure_run_store
    store = ensure_run_store()
    store.add_usage_event(run_id="ws:shot1", kind="paid_call", tool="text_to_image",
                          amount_usd=0.039, reason="wavespeed-ai/flux-dev", status="done", call_id="ws:shot1")
    store.add_usage_event(run_id="ws:shot2", kind="paid_call", tool="image_edit",
                          amount_usd=0.12, reason="openai/gpt-image-edit", status="done", call_id="ws:shot2")

    async with pw.async_playwright() as p:
        try:
            browser, pg = await _open(p, app_url, "zh", "light")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await pg.wait_for_selector("[data-testid=home-shell]", timeout=20000)
        await pg.wait_for_timeout(800)
        # wait for balance chip if possible
        await pg.locator("[data-testid=rail-settings]").click()
        await pg.locator("[data-testid=settings-menu]").wait_for(timeout=10000)
        await pg.wait_for_timeout(400)
        await _shot(pg, "menu-zh-light")

        # language submenu
        await pg.locator("[data-testid=settings-lang]").hover()
        await pg.locator("[data-testid=settings-lang-fly]").wait_for(timeout=5000)
        await pg.wait_for_timeout(200)
        await _shot(pg, "menu-lang-zh-light")

        # theme submenu
        await pg.locator("[data-testid=settings-theme]").hover()
        await pg.locator("[data-testid=settings-theme-fly]").wait_for(timeout=5000)
        await pg.wait_for_timeout(200)
        await _shot(pg, "menu-theme-zh-light")

        # usage modal
        bal = pg.locator("[data-testid=settings-usage]")
        if await bal.count():
            await bal.click()
            await pg.locator(".ca-usage").wait_for(timeout=10000)
            await pg.wait_for_timeout(400)
            await _shot(pg, "usage-zh-light")
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(200)
        await browser.close()


@pytest.mark.asyncio
async def test_78_shots_en_dark_menu_usage(app_url, fake_tools, monkeypatch, mock_ws):  # noqa: F811
    from ComfyArt.api import wavespeed
    async def _bal(key): return 8.50
    monkeypatch.setattr(wavespeed, "fetch_balance", _bal)

    async with pw.async_playwright() as p:
        try:
            browser, pg = await _open(p, app_url, "en", "dark")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await pg.wait_for_selector("[data-testid=home-shell]", timeout=20000)
        await pg.wait_for_timeout(800)
        await pg.locator("[data-testid=rail-settings]").click()
        await pg.locator("[data-testid=settings-menu]").wait_for(timeout=10000)
        await pg.wait_for_timeout(400)
        await _shot(pg, "menu-en-dark")

        await pg.locator("[data-testid=settings-lang]").hover()
        await pg.locator("[data-testid=settings-lang-fly]").wait_for(timeout=5000)
        await pg.wait_for_timeout(200)
        await _shot(pg, "menu-lang-en-dark")

        await pg.locator("[data-testid=settings-theme]").hover()
        await pg.locator("[data-testid=settings-theme-fly]").wait_for(timeout=5000)
        await pg.wait_for_timeout(200)
        await _shot(pg, "menu-theme-en-dark")

        bal = pg.locator("[data-testid=settings-usage]")
        if await bal.count():
            await bal.click()
            await pg.locator(".ca-usage").wait_for(timeout=10000)
            await pg.wait_for_timeout(400)
            await _shot(pg, "usage-en-dark")
        await browser.close()


@pytest.mark.asyncio
async def test_78_shots_en_light_menu(app_url, fake_tools, monkeypatch, mock_ws):  # noqa: F811
    from ComfyArt.api import wavespeed
    async def _bal(key): return 12.34
    monkeypatch.setattr(wavespeed, "fetch_balance", _bal)

    async with pw.async_playwright() as p:
        try:
            browser, pg = await _open(p, app_url, "en", "light")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await pg.wait_for_selector("[data-testid=home-shell]", timeout=20000)
        await pg.wait_for_timeout(600)
        await pg.locator("[data-testid=rail-settings]").click()
        await pg.locator("[data-testid=settings-menu]").wait_for(timeout=10000)
        await pg.wait_for_timeout(350)
        await _shot(pg, "menu-en-light")
        await browser.close()

