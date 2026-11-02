"""#581 #78 AFTER tip-pin — skill card author usage + modal creator/meta/share.

Prefer:
  DESIGN_581_78_SHOOT=1 PYTHONPATH=.. pytest -q tests/test_design_581_78_shots.py -s
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "left-ours"

SHOTS = [
    "AFTER-skills-card-author-no-usage-zh-light.png",
    "AFTER-skills-card-author-with-usage-zh-light.png",
    "AFTER-skills-card-author-en-dark.png",
    "AFTER-skill-modal-creator-meta-zh-light.png",
]


async def _goto_skills(pg, *, lang: str, theme: str, app_url: str, usage: dict | None = None) -> None:
    usage_js = ""
    if usage:
        import json
        usage_js = f"localStorage.setItem('comfyart.skillUsage',{json.dumps(json.dumps(usage))});"
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        "localStorage.setItem('comfyart.rail.collapsed','0');"
        + usage_js
    )
    await pg.goto(app_url)
    await pg.get_by_test_id("rail-skills").wait_for()
    await pg.get_by_test_id("rail-skills").click()
    await pg.get_by_test_id("skills-page").wait_for()
    await pg.get_by_test_id("skills-wall-card").first.wait_for()
    await pg.wait_for_timeout(700)


async def _card_author_clip(pg, skill_id: str | None = None) -> dict:
    sel = f'[data-testid="skills-wall-card"][data-skill="{skill_id}"]' if skill_id else '[data-testid="skills-wall-card"]'
    box = await pg.locator(sel).first.bounding_box()
    assert box
    # pad a bit around the full card so author row is readable
    return {
        "x": max(0, box["x"] - 8),
        "y": max(0, box["y"] - 8),
        "width": min(420, box["width"] + 16),
        "height": min(520, box["height"] + 16),
    }


async def capture(app_url: str) -> None:
    from playwright.async_api import async_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # 1) zh-light — no usage (fresh store): author row without usage stat
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        pg = await ctx.new_page()
        await _goto_skills(pg, lang="zh", theme="light", app_url=app_url)
        # pick product card if present (has dialog); else first card
        product = pg.locator('[data-testid="skills-wall-card"][data-skill="product"]')
        card = product if await product.count() else pg.get_by_test_id("skills-wall-card").first
        await card.scroll_into_view_if_needed()
        await pg.wait_for_timeout(300)
        # assert no usage badge when empty
        n_usage = await pg.locator('[data-testid="skills-card-usage"]').count()
        print("usage badges (empty store)=", n_usage)
        assert n_usage == 0
        clip = await _card_author_clip(pg, "product" if await product.count() else None)
        await pg.screenshot(path=str(OUT / SHOTS[0]), clip=clip)
        print("wrote", OUT / SHOTS[0])
        await ctx.close()

        # 2) zh-light — with real usage for product
        ctx2 = await browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        pg2 = await ctx2.new_page()
        await _goto_skills(pg2, lang="zh", theme="light", app_url=app_url, usage={"product": 3})
        product2 = pg2.locator('[data-testid="skills-wall-card"][data-skill="product"]')
        await product2.scroll_into_view_if_needed()
        await pg2.wait_for_timeout(400)
        usage_el = product2.locator('[data-testid="skills-card-usage"]')
        await usage_el.wait_for()
        text = await usage_el.inner_text()
        print("product usage text=", text)
        assert "3" in text
        # no fav count
        assert await pg2.locator('[data-testid="skills-card-fav-count"]').count() == 0
        clip2 = await _card_author_clip(pg2, "product")
        await pg2.screenshot(path=str(OUT / SHOTS[1]), clip=clip2)
        print("wrote", OUT / SHOTS[1])
        await ctx2.close()

        # 3) en-dark — with usage
        ctx3 = await browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        pg3 = await ctx3.new_page()
        await _goto_skills(pg3, lang="en", theme="dark", app_url=app_url, usage={"product": 2})
        product3 = pg3.locator('[data-testid="skills-wall-card"][data-skill="product"]')
        await product3.scroll_into_view_if_needed()
        await pg3.wait_for_timeout(400)
        await product3.locator('[data-testid="skills-card-usage"]').wait_for()
        clip3 = await _card_author_clip(pg3, "product")
        await pg3.screenshot(path=str(OUT / SHOTS[2]), clip=clip3)
        print("wrote", OUT / SHOTS[2])
        await ctx3.close()

        # 4) modal creator + meta (zh-light, usage seeded so joined meta shows)
        ctx4 = await browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
        pg4 = await ctx4.new_page()
        await _goto_skills(pg4, lang="zh", theme="light", app_url=app_url, usage={"product": 2})
        product4 = pg4.locator('[data-testid="skills-wall-card"][data-skill="product"]')
        await product4.scroll_into_view_if_needed()
        await product4.click()
        await pg4.get_by_test_id("skill-run-dialog").wait_for()
        await pg4.get_by_test_id("skill-run-share").wait_for()
        await pg4.get_by_test_id("skill-run-favourite").wait_for()
        meta = await pg4.get_by_test_id("skill-run-meta").inner_text()

        print("modal meta=", meta)
        assert "已使用" in meta and "模板" in meta
        # crop dialog card
        # element shot of dialog — then we keep a top strip for tip-pin readability
        dlg_path = OUT / SHOTS[3]
        await pg4.get_by_test_id("skill-run-dialog").screenshot(path=str(dlg_path))
        # crop top of that png to creator/meta (Pillow)
        from PIL import Image
        im = Image.open(dlg_path)
        w, h = im.size
        im.crop((0, 0, min(w, 720), min(h, 220))).save(dlg_path)
        print("wrote", OUT / SHOTS[3])
        await ctx4.close()
        await browser.close()


if __name__ == "__main__":
    raise SystemExit("Use: DESIGN_581_78_SHOOT=1 pytest -q tests/test_design_581_78_shots.py -s")
