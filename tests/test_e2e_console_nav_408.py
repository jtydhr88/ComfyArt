"""#408 e2e: WaveSpeed console task-history entry (#498: via SettingsMenu + project header)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools, pytestmark  # noqa: F401

HISTORY = "https://wavespeed.ai/history"
OUT = Path(os.environ.get("SHOT_OUT", "/workspace/ComfyArt/408/console-nav"))


async def _shot(pg, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    await pg.screenshot(path=str(OUT / f"{name}.png"))


async def _open(p, app_url, lang: str, theme: str, path: str = "/"):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        "localStorage.setItem('comfyart.e2e','1');"
        "window.__opened=[];"
        "window.open=function(url){window.__opened.push(String(url));return null};"
    )
    await pg.goto(app_url.rstrip("/") + path)
    return browser, pg


@pytest.mark.asyncio
async def test_home_settings_zh_light_opens_history(app_url, fake_tools, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _open(p, app_url, "zh", "light")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await pg.wait_for_selector("[data-testid=home-shell]", timeout=20000)
        assert await pg.locator("[data-testid=rail-ws-history]").count() == 0
        await pg.locator("[data-testid=rail-settings]").click()
        btn = pg.locator("[data-testid=settings-ws-history]")
        await btn.wait_for(timeout=10000)
        await btn.hover()
        await pg.wait_for_timeout(300)
        await _shot(pg, "home-settings-zh-light")
        await btn.click()
        assert await pg.evaluate("() => window.__opened") == [HISTORY]
        await browser.close()


@pytest.mark.asyncio
async def test_home_settings_en_dark_and_project_menu(app_url, fake_tools, monkeypatch):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        try:
            browser, pg = await _open(p, app_url, "en", "dark")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await pg.wait_for_selector("[data-testid=home-shell]", timeout=20000)
        await pg.locator("[data-testid=rail-settings]").click()
        btn = pg.locator("[data-testid=settings-ws-history]")
        await btn.wait_for(timeout=10000)
        text = await btn.inner_text()
        assert "WaveSpeed" in text and "task history" in text.lower()
        await btn.hover()
        await pg.wait_for_timeout(300)
        await _shot(pg, "home-settings-en-dark")
        await browser.close()

        try:
            browser, pg = await _open(p, app_url, "en", "dark", "/?project=e408nav&new=1")
        except Exception as e:
            pytest.skip(f"chromium not available: {e}")
        await pg.wait_for_selector(".ca-head__logo", timeout=20000)
        await pg.locator(".ca-head__logo").click()
        menu_item = pg.locator("[data-testid=menu-ws-history]")
        await menu_item.wait_for(timeout=10000)
        text = await menu_item.inner_text()
        assert "WaveSpeed" in text and "task history" in text.lower()
        await _shot(pg, "project-menu-en-dark")
        await menu_item.click()
        opened = await pg.evaluate("() => window.__opened")
        assert HISTORY in opened, opened
        await browser.close()
