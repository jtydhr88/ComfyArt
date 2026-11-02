"""#494-1 e2e: Explore cards from real data, category chips, bookmark, old personal skill (mock only, $0)."""
from __future__ import annotations

import json
import re
import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
BRAND_NAME = re.search(r"name: '([^']+)'", (Path(__file__).resolve().parents[1] / "src/brand.ts").read_text()).group(1)

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("SKILL_CARDS_SHOTS")
OLD_MD = "---\nname: 旧技能\ndescription: 老的个人技能\n---\nDo things.\n"
IMG_MD = "---\nname: 有图技能\ndescription: 图片可加载\n---\nDo things.\n"
GOOD_WEBP = (Path(__file__).resolve().parents[1] / "public/skills/poster/cover.webp").read_bytes()


async def _seed_personal(pg):
    async def handle(route):
        url = route.request.url
        if "userdata?dir=comfyart%2Fskills" in url:
            return await route.fulfill(json=["old-skill/SKILL.md", "old-skill/images.json",
                                             "img-skill/SKILL.md", "img-skill/images.json"])
        if "SKILL.md" in url:
            return await route.fulfill(body=IMG_MD if "img-skill" in url else OLD_MD)
        if "images.json" in url:
            # old-skill: images[0] points at a file that does not exist (broken image → placeholder)
            return await route.fulfill(body=json.dumps({"good.png": "input/good.png"} if "img-skill" in url
                                                       else {"ref.png": "input/missing-494/ref.png"}))
        return await route.fallback()
    await pg.route(re.compile(r"/userdata"), handle)  # glob `*` stops at `?`; match the query too

    async def thumb(route):
        if "good.png" in route.request.url:
            return await route.fulfill(body=GOOD_WEBP, content_type="image/webp")
        return await route.fulfill(status=404, body="")
    await pg.route(re.compile(r"/comfyart/thumb\?"), thumb)


async def _open(p, app_url, lang, theme="light"):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1440, "height": 900})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    await _seed_personal(pg)
    await pg.goto(app_url + "?view=skills")
    await pg.get_by_test_id("skills-wall-card").first.wait_for()
    return browser, pg


async def _shot(pg, name):
    if SHOTS:
        await pg.wait_for_timeout(400)
        await pg.screenshot(path=f"{SHOTS}/{name}.png")


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_cards_chips_bookmark(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme)
        cards = pg.get_by_test_id("skills-wall-card")
        assert await cards.count() == 50  # #591 + #634 + #640 Phase3-S1
        await pg.locator('[data-skill="custom-workflow"]').scroll_into_view_if_needed()  # #581: last card now has its own cover
        await _shot(pg, f"list-{lang}-{theme}")
        chips = await pg.get_by_test_id("skills-chips").locator("button").all_inner_texts()
        zh_chips, en_chips = ['为你推荐', '电商', '品牌', '社交媒体', '网站', '广告创意'], ['For you', 'E-commerce', 'Branding', 'Social Media', 'Website', 'Ads & Creative']
        assert chips == (zh_chips if lang == "zh" else en_chips)
        assert await pg.get_by_test_id("skills-chip-website").count() == 1  # #591 mobile-ui/web-product
        await pg.get_by_test_id("skills-chip-ecommerce").click()
        assert sorted(await cards.evaluate_all("cs => cs.map(c => c.dataset.skill)")) == ["ai-model", "clothing-swap", "commerce-strategist", "lifestyle-scene", "live-promo-decor", "multi-angle", "packaging", "person-swap", "pose-fission", "product", "product-to-packaging", "promo-ecommerce", "studio-model", "taobao-product"]  # #634 + #640 Phase3 ecommerce builtins
        await _shot(pg, f"chip-ecommerce-{lang}-{theme}")
        await pg.get_by_test_id("skills-chip-forYou").click()
        cw = pg.locator('[data-skill="custom-workflow"]')
        # #581 — custom-workflow has a real cover now (manifest 7237c371); placeholder only for cover-less user skills.
        assert await cw.get_by_test_id("skills-card-placeholder").count() == 0
        assert "494/covers-v3/custom-workflow.webp" in (await cw.get_by_test_id("skills-card-cover").get_attribute("src") or "")
        # #494/#529 — kind badge on every Explore card (bottom-left). Built-ins with `video` → data-kind=video;
        # custom-workflow (no video) stays image. Never invent a video badge without data.
        assert await cards.locator(".ca-swall__cover [data-testid=skills-card-kind]").count() == 50
        box, badge = await cw.locator(".ca-swall__cover").bounding_box(), await cw.get_by_test_id("skills-card-kind").bounding_box()
        assert badge["x"] - box["x"] < 16 and (box["y"] + box["height"]) - (badge["y"] + badge["height"]) < 16
        assert await cw.get_by_test_id("skills-card-kind").get_attribute("data-kind") == "image"
        assert await cw.get_by_test_id("skills-card-video").count() == 0
        assert await cw.locator(".ca-swall__cover").evaluate(  # placeholder CSS still resolves to --ca-text-2
            "c => { const e = document.createElement('span'); e.className = 'ca-swall__placeholder'; c.append(e);"
            " const p = document.createElement('i'); p.style.color = 'var(--ca-text-2)'; e.parentNode.append(p);"
            " const ok = getComputedStyle(e).color === getComputedStyle(p).color; p.remove(); e.remove(); return ok }")
        poster = pg.locator('[data-skill="poster"]')
        src = await poster.get_by_test_id("skills-card-cover").get_attribute("src")
        assert "494/covers-v3/poster.webp" in (src or "")
        assert await pg.evaluate("s => fetch(s).then(r => r.status)", src) == 200
        assert await poster.get_by_test_id("skills-card-cover").get_attribute("alt") == await poster.locator("h3").inner_text()
        assert await poster.get_by_test_id("skills-card-author").inner_text() == BRAND_NAME
        assert await poster.get_by_test_id("skills-card-kind").count() == 1
        assert await poster.get_by_test_id("skills-card-kind").get_attribute("data-kind") == "video"
        assert await poster.get_by_test_id("skills-card-video").count() == 1
        vsrc = await poster.get_by_test_id("skills-card-video").get_attribute("src")
        assert "494/wash/videos/poster.mp4" in (vsrc or "")
        await poster.hover()
        assert await poster.get_by_test_id("skills-card-bookmark").is_visible()
        # #494-2 — hover 「试用此技能」 is intentional; #529 only mounts video + badge.
        assert await poster.get_by_test_id("skills-card-try").is_visible()
        await _shot(pg, f"hover-{lang}-{theme}")
        before = pg.url
        await poster.get_by_test_id("skills-card-bookmark").click()
        assert pg.url == before  # bookmark only toggles favourite
        assert "poster" in await pg.evaluate("localStorage.getItem('comfyart.skillFavourites')")
        await pg.get_by_test_id("skills-tab-favourites").click()
        assert await cards.evaluate_all("cs => cs.map(c => c.dataset.skill)") == ["poster"]
        await browser.close()


@pytest.mark.parametrize("lang,theme", [("zh", "dark"), ("en", "light")])
async def test_old_personal_skill_renders(app_url, lang, theme):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang, theme)
        await pg.get_by_test_id("skills-tab-personal").click()
        card = pg.locator('[data-skill="old-skill"]')
        await card.wait_for()
        # 46df37d: personal tab renders row cards — no author / kind badge / bookmark by design
        assert await card.get_attribute("data-layout") == "row"
        assert await card.get_attribute("data-custom") is not None
        assert await card.locator(".ca-swall__title").is_visible()
        assert (await card.locator(".ca-swall__title").inner_text()).strip()
        assert await card.get_by_test_id("skills-card-author").count() == 0
        # images[0] fails to load → same placeholder as a card without image; no broken img / alt text
        await card.get_by_test_id("skills-card-placeholder").wait_for(state="visible")
        assert await card.get_by_test_id("skills-card-cover").count() == 0
        assert await card.locator("img").count() == 0
        assert await card.get_by_test_id("skills-card-placeholder").locator("svg").count() == 1
        await _shot(pg, f"personal-old-{lang}-{theme}")
        # old import with a loadable images.json entry → its own images[0] via thumb (AC 5), no migration
        ok = pg.locator('[data-skill="img-skill"]')
        img = ok.get_by_test_id("skills-card-cover")
        await img.wait_for(state="visible")
        assert "good.png" in (await img.get_attribute("src"))
        await pg.wait_for_function("e => e.complete && e.naturalWidth > 0", arg=await img.element_handle())
        assert await ok.get_by_test_id("skills-card-placeholder").count() == 0
        assert "社" + "区" not in await card.inner_text()
        await browser.close()
