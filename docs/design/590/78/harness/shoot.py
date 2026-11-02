"""#590 #78 AFTER tip-pin — home explore/feed masonry wash-v2 featured tiles.

Run from repo root:
  DESIGN_590_78_SHOOT=1 ~/.comfyart-runtime/venv/bin/python -m pytest -q tests/test_design_590_78_shots.py -s
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "left-ours"

SHOTS = [
    "AFTER-home-featured-masonry-zh-light-1280.png",
    "AFTER-home-featured-masonry-en-dark-1280.png",
    "AFTER-home-featured-branding-chip-zh-light-1280.png",
    "AFTER-home-featured-ads-chip-en-dark-1280.png",
]

FEED_PIN = "0e92302302de2102ab6f66aa7633a40945a381c7"


async def _open(p, app_url: str, *, lang: str, theme: str):
    browser = await p.chromium.launch()
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
    pg = await ctx.new_page()
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        "localStorage.setItem('comfyart.rail.collapsed','0');"
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("home-featured").wait_for()
    await pg.get_by_test_id("home-chip-forYou").click()
    await pg.wait_for_timeout(200)
    feat = pg.get_by_test_id("home-featured")
    await feat.scroll_into_view_if_needed()
    await pg.wait_for_function(
        "()=>{const i=document.querySelector('[data-testid=home-featured-card] img');"
        "return i&&i.complete&&i.naturalWidth>0}",
        timeout=45000,
    )
    await pg.wait_for_function(
        f"()=>[...document.querySelectorAll('[data-testid=home-featured-card] img')]"
        f".some(i=> (i.currentSrc||i.src||'').includes('{FEED_PIN}') && i.complete && i.naturalWidth>0)",
        timeout=45000,
    )
    await pg.wait_for_timeout(800)
    return browser, ctx, pg


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b, ctx, pg = await _open(p, app_url, lang="zh", theme="light")
        await pg.screenshot(path=str(OUT / SHOTS[0]))
        print("wrote", OUT / SHOTS[0])

        await pg.get_by_test_id("home-chip-branding").click()
        await pg.wait_for_timeout(500)
        await pg.wait_for_function(
            "()=>{const i=document.querySelector('[data-testid=home-featured-card] img');"
            "return i&&i.complete&&i.naturalWidth>0}",
            timeout=30000,
        )
        await pg.wait_for_timeout(600)
        await pg.screenshot(path=str(OUT / SHOTS[2]))
        print("wrote", OUT / SHOTS[2])
        await ctx.close()
        await b.close()

        b2, ctx2, pg2 = await _open(p, app_url, lang="en", theme="dark")
        await pg2.screenshot(path=str(OUT / SHOTS[1]))
        print("wrote", OUT / SHOTS[1])

        await pg2.get_by_test_id("home-chip-ads").click()
        await pg2.wait_for_timeout(500)
        await pg2.wait_for_function(
            "()=>{const i=document.querySelector('[data-testid=home-featured-card] img');"
            "return i&&i.complete&&i.naturalWidth>0}",
            timeout=30000,
        )
        await pg2.wait_for_timeout(600)
        await pg2.screenshot(path=str(OUT / SHOTS[3]))
        print("wrote", OUT / SHOTS[3])
        await ctx2.close()
        await b2.close()
