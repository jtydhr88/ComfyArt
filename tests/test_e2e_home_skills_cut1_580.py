"""#580 cut 1 e2e @1280x800 (sidebar expanded, home column 928): 6 quick-start cards ≈141 wide (cover 141×106, 4:3),
gap 16, no horizontal scroll; Skill 案例 masonry 3 columns ≈299 wide, gap 16, no repeated skill. Mock only, $0."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")


async def _measure(app_url, width, *, collapsed=False):
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": width, "height": 800})).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.rail.collapsed','{'1' if collapsed else '0'}');")
        await pg.goto(app_url)
        await pg.get_by_test_id("home-featured-grid").wait_for()
        await pg.wait_for_timeout(200)
        m = await pg.evaluate(
            """() => {
              const b = (el) => { const q = el.getBoundingClientRect(); return {x: q.x, w: q.width, h: q.height}; };
              const grid = document.querySelector('.ca-skillgrid');
              const cards = [...grid.querySelectorAll('.ca-skillcard')].map(b);
              const covers = [...document.querySelectorAll('[data-testid="home-skill-cover"]')].map(b);
              const cols = [...document.querySelectorAll('[data-testid="home-featured-col"]')].filter(c => c.children.length).map(b);
              const allCols = [...document.querySelectorAll('[data-testid="home-featured-col"]')].map(b);
              const tiles = [...document.querySelectorAll('[data-testid="home-featured-card"]')]
                .sort((a, b) => a.dataset.order - b.dataset.order).map(e => ({skill: e.dataset.skill, preset: e.dataset.preset || null, img: e.querySelector('img').getAttribute('src')}));
              const colSkills = [...document.querySelectorAll('[data-testid="home-featured-col"]')].map(c =>
                [...c.querySelectorAll('[data-testid="home-featured-card"]')]
                  .sort((a, b) => a.getBoundingClientRect().y - b.getBoundingClientRect().y).map(e => e.dataset.skill));
              const domSkills = [...document.querySelectorAll('[data-testid="home-featured-card"]')].map(e => e.dataset.skill);
              return {grid: b(grid), scroll: grid.scrollWidth - grid.clientWidth, cards, covers, cols: allCols, tiles, colSkills, domSkills};
            }"""
        )
        await browser.close()
        return m


async def test_cut1_1280_expanded(app_url):  # noqa: F811
    m = await _measure(app_url, 1280)
    assert abs(m["grid"]["w"] - 928) <= 1
    assert len(m["cards"]) == 6 and m["scroll"] <= 0
    for c in m["cards"]:
        assert abs(c["w"] - 141) <= 1.5, c
    for a, b in zip(m["cards"], m["cards"][1:]):
        assert abs(b["x"] - (a["x"] + a["w"]) - 16) <= 0.6
    for cv in m["covers"]:
        assert abs(cv["w"] - 141) <= 1.5 and abs(cv["h"] - 106) <= 1.5, cv
    assert len(m["cols"]) == 3, m["cols"]
    for c in m["cols"]:
        assert abs(c["w"] - 299) <= 1.5, c
    for a, b in zip(m["cols"], m["cols"][1:]):
        assert abs(b["x"] - (a["x"] + a["w"]) - 16) <= 0.6
    _check_tiles(m["tiles"])
    _check_columns(m)


async def test_cut1_1920_five_columns(app_url):  # noqa: F811
    m = await _measure(app_url, 1920)
    assert len(m["cards"]) == 6 and m["scroll"] <= 0
    assert len(m["cols"]) == 5
    _check_tiles(m["tiles"])
    _check_columns(m)


# #595 Phase1 mount: upgrade9 + new6 + interior (custom-workflow has no featured[]). featured-v1 (cut1) + featured-v2 (new6).
PHASE1_FEATURED = {
    "product", "multi-angle", "brand", "character", "logo-material", "packaging",
    "motion", "meta-ads", "poster", "thumbnail", "mobile-ui", "social",
    "marketing-campaign", "web-product", "banner", "interior",
}


def _featured_from_data():
    """Every builtin with feed cases: featured[] or still examples (#595 Phase1 + #637 B5 + #636 C5 + #643 thumbnail)."""
    import re
    src = (Path(__file__).resolve().parents[1] / "src/skills.ts").read_text()
    a = src.index("export const BUILTIN_SKILLS")
    block = src[a:src.find("\n]", a)]
    out = set()
    for p in re.split(r"\n  \{ id: '", block)[1:]:
        m = re.search(r"featured: (\[\]|\w+\()", p)
        # skillFeaturedCases: featured[] first, else still examples (e.g. #643 NEW19 ex643)
        if (m and m.group(1) != "[]") or re.search(r"examples: ex\d+\(", p):
            out.add(p.split("'", 1)[0])
    return out


# Fixed expectation (#689 follow-up): pinned id list so a skill silently dropping out of the
# feed fails here; _featured_from_data() is only a drift guard against src/skills.ts.
FEED_EXPECTED = frozenset({
    "anim-2d", "banner", "before-after", "brand", "character", "clothing-swap", "commerce-strategist", "creator-identity",
    "flash-cut-video", "interior", "lifestyle-scene", "linkedin-banner", "logo-abstract",
    "logo-material", "marketing-campaign", "meta-ads", "mobile-ui", "motion", "multi-angle",
    "naive-illustration", "packaging", "person-swap", "photo-split-poster", "portrait-studio", "poster",
    "ppt-visual", "product", "product-website", "promo-ecommerce", "social", "style-transfer",
    "taobao-product", "thumbnail", "web-product", "youtube-channel-banner",
    "animated-poster",  # #643 per-slot PR (examples wired => in feed)
    "premium-website",  # #643 per-slot PR (examples wired => in feed)
    "studio-model",  # #643 per-slot PR (examples wired => in feed)
})
FEED_MIN = 38  # +#677/#682/#674/#678 + #643 animated-poster + premium-website + studio-model


FEATURED_DIRS = ("/580/featured-v1/", "/580/featured-v2/", "/637/wash/", "/636/wash/", "/643/wash/")


def _check_tiles(tiles):
    skills = [t["skill"] for t in tiles]
    assert PHASE1_FEATURED <= FEED_EXPECTED
    assert set(skills) == FEED_EXPECTED, sorted(set(skills) ^ FEED_EXPECTED)
    assert len(set(skills)) == len(FEED_EXPECTED) == FEED_MIN
    assert _featured_from_data() == FEED_EXPECTED, "skills.ts feed drifted: update FEED_EXPECTED deliberately"
    # #588/#594 featured-v1/v2; later phases pin their own wash dirs (#637 B5, #636 C5, #643 thumbnail)
    assert all(any(d in t["img"] for d in FEATURED_DIRS) for t in tiles), [t["img"] for t in tiles]
    assert all(a != b for a, b in zip(skills, skills[1:])), skills  # data order: no adjacent duplicates
    assert len({t["img"] for t in tiles}) == len(tiles)
    assert len(tiles) > len(PHASE1_FEATURED)  # second round follows
    n = len(PHASE1_FEATURED)
    assert len(set(skills[:n])) == n  # first round: one per skill
    first_char = next(t for t in tiles if t["skill"] == "character")
    assert "/580/featured-v1/character/01.webp" in first_char["img"]  # #588 featured[] supersedes featuredPreset
    # #595 hot mount: first featured tile is the first Phase1 hot id with featured (product)
    assert skills[0] == "product"


def _check_columns(m):
    # #580 QA: no adjacent duplicates in each rendered column (visual top→bottom order) and in DOM order
    for col in m["colSkills"]:
        assert all(a != b for a, b in zip(col, col[1:])), m["colSkills"]
    dom = m["domSkills"]
    assert all(a != b for a, b in zip(dom, dom[1:])), dom


async def test_cut1_example_tile_opens_dialog(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
        await pg.goto(app_url)
        card = pg.locator('[data-testid="home-featured-card"]:not([data-preset])').first
        await card.wait_for()
        skill = await card.get_attribute("data-skill")
        await card.click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        assert await dlg.get_attribute("data-skill") == skill
        await browser.close()
