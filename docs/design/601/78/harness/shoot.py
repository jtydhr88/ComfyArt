"""#601 #78 AFTER tip-pin — SkillRun soft FU: header≠CTA, filmstrip 01…, Share/Bookmark.

Prefer:
  DESIGN_601_78_SHOOT=1 PYTHONPATH=.. /workspace/.venv-589/bin/python -m pytest -q tests/test_design_601_78_shots.py -s
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "left-ours"

SHOTS = [
    "AFTER-skill-modal-header-cta-filmstrip-zh-light.png",
    "AFTER-skill-modal-header-cta-share-bookmark-en-dark.png",
    "AFTER-skill-modal-filmstrip-pad-crop-zh-light.png",
    "AFTER-skill-modal-righthead-cta-crop-zh-light.png",
]


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # 1) zh-light — multi-angle dialog (examples filmstrip + dual-col header/CTA + share/fav)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
        pg = await ctx.new_page()
        await pg.add_init_script(
            "localStorage.setItem('comfyart.lang','zh');"
            "localStorage.setItem('comfyart.theme','light');"
            "localStorage.setItem('comfyart.rail.collapsed','0');"
        )
        await pg.goto(app_url)
        await pg.get_by_test_id("home-start-skill").wait_for()
        card = pg.locator('[data-testid="home-skill-card"][data-skill="multi-angle"]')
        if await card.count() == 0:
            # fallback: open skills wall
            await pg.get_by_test_id("rail-skills").click()
            await pg.get_by_test_id("skills-wall-card").first.wait_for()
            card = pg.locator('[data-testid="skills-wall-card"][data-skill="multi-angle"]')
            if await card.count() == 0:
                card = pg.get_by_test_id("skills-wall-card").first
        await card.first.click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        await pg.get_by_test_id("skill-run-header").wait_for()
        header = await pg.get_by_test_id("skill-run-header").inner_text()
        cta = await pg.get_by_test_id("skill-run-go").inner_text()
        print("zh header/cta=", header, "/", cta)
        assert header == "开始创作" and cta == "开始制作"
        assert await pg.get_by_test_id("skill-run-share").count() == 1
        assert await pg.get_by_test_id("skill-run-favourite").count() == 1
        # filmstrip pad if examples present
        thumbs = pg.get_by_test_id("skill-run-example-thumb")
        if await thumbs.count() > 0:
            nums = await pg.locator(".ca-skillrun__thumbnum").all_inner_texts()
            print("zh filmstrip=", nums[:5])
            assert all(len(n) >= 2 and n[0].isdigit() for n in nums)
            assert nums[0] == "01"
        await pg.wait_for_timeout(600)
        await dlg.screenshot(path=str(OUT / SHOTS[0]))
        print("wrote", OUT / SHOTS[0])

        # crop filmstrip
        strip = pg.locator(".ca-skillrun__strip")
        if await strip.count():
            box = await strip.bounding_box()
            if box:
                await pg.screenshot(
                    path=str(OUT / SHOTS[2]),
                    clip={
                        "x": max(0, box["x"] - 8),
                        "y": max(0, box["y"] - 8),
                        "width": min(700, box["width"] + 16),
                        "height": min(160, box["height"] + 16),
                    },
                )
                print("wrote", OUT / SHOTS[2])

        # crop right head + CTA
        right = pg.locator(".ca-skillrun__right")
        box = await right.bounding_box()
        if box:
            await pg.screenshot(
                path=str(OUT / SHOTS[3]),
                clip={
                    "x": max(0, box["x"]),
                    "y": max(0, box["y"]),
                    "width": min(420, box["width"]),
                    "height": min(800, box["height"]),
                },
            )
            print("wrote", OUT / SHOTS[3])
        await ctx.close()

        # 2) en-dark — same dialog
        ctx2 = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
        pg2 = await ctx2.new_page()
        await pg2.add_init_script(
            "localStorage.setItem('comfyart.lang','en');"
            "localStorage.setItem('comfyart.theme','dark');"
            "localStorage.setItem('comfyart.rail.collapsed','0');"
        )
        await pg2.goto(app_url)
        await pg2.get_by_test_id("home-start-skill").wait_for()
        card2 = pg2.locator('[data-testid="home-skill-card"][data-skill="multi-angle"]')
        if await card2.count() == 0:
            await pg2.get_by_test_id("rail-skills").click()
            await pg2.get_by_test_id("skills-wall-card").first.wait_for()
            card2 = pg2.locator('[data-testid="skills-wall-card"][data-skill="multi-angle"]')
            if await card2.count() == 0:
                card2 = pg2.get_by_test_id("skills-wall-card").first
        await card2.first.click()
        dlg2 = pg2.get_by_test_id("skill-run-dialog")
        await dlg2.wait_for()
        header2 = await pg2.get_by_test_id("skill-run-header").inner_text()
        cta2 = await pg2.get_by_test_id("skill-run-go").inner_text()
        print("en header/cta=", header2, "/", cta2)
        assert header2 == "Start Creating" and cta2 == "Start making"
        await pg2.wait_for_timeout(600)
        await dlg2.screenshot(path=str(OUT / SHOTS[1]))
        print("wrote", OUT / SHOTS[1])
        await ctx2.close()
        await browser.close()
