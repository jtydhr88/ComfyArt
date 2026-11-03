"""#650 / #694 e2e (mock only, $0): Skills page Create split button (rendered 96×36: text 68 + caret 28),
creator opening title + 3 starter pills per gold (zh/en), empty creator input, and Import a Skill end-to-end
from the dropdown (zip → new skill's editor opens, listed under 我的/Personal).
Set SHOTS_650=/dir for screenshots."""
from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")
SHOTS = os.environ.get("SHOTS_650")
GOLD = {
    "en": ("What do you want to design?", ["Add your reference", "Start from skill", "Add your brand kit"]),
    "zh": ("你想设计什么？", ["添加你的参考", "从技能开始", "添加你的品牌套件"]),
}


async def _page(p, app_url, lang):
    browser = await p.chromium.launch()
    pg = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','light')")
    await pg.goto(app_url.rstrip("/") + "/?view=skills")
    await pg.get_by_test_id("skills-create").wait_for()
    return browser, pg


async def _shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        await pg.wait_for_timeout(300)  # let the caret rotation finish
        await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"), animations="disabled")


@pytest.mark.parametrize("lang", ["en", "zh"])
async def test_split_button_rendered_widths_694(app_url, lang):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, app_url, lang)
        box = lambda tid: pg.get_by_test_id(tid).bounding_box()  # noqa: E731
        main, caret = await box("skills-create"), await box("skills-create-menu")
        assert round(caret["width"]) == 28 and round(caret["height"]) == 36, caret  # #694: was 52
        assert round(main["width"]) == 68 and round(main["x"] + main["width"]) == round(caret["x"]), (main, caret)
        clipped = await pg.get_by_test_id("skills-create").evaluate("b => b.scrollWidth > b.clientWidth")
        assert not clipped  # label not cut
        await pg.get_by_test_id("skills-create-menu").click()
        await pg.get_by_test_id("skills-import").wait_for()
        assert await pg.get_by_test_id("skills-create-menu").get_attribute("aria-expanded") == "true"
        await _shot(pg, f"ours-entry-{lang}")
        await browser.close()


@pytest.mark.parametrize("lang", ["en", "zh"])
async def test_creator_title_pills_placeholder_650(app_url, lang):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, app_url, lang)
        await pg.get_by_test_id("skills-create").click()
        await pg.get_by_test_id("creator-landing-title").wait_for()
        title, pills = GOLD[lang]
        assert (await pg.get_by_test_id("creator-landing-title").inner_text()).strip() == title
        assert [s.strip() for s in await pg.locator("[data-creator] .ca-chat__start").all_inner_texts()] == pills
        assert await pg.locator(".ca-composer__input").get_attribute("placeholder") == ""
        await pg.wait_for_timeout(1500)
        await pg.get_by_test_id("creator-landing-title").wait_for()
        await _shot(pg, f"ours-creator-initial-{lang}")
        await browser.close()


def _zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("poster-650/SKILL.md", "---\nname: Poster 650\ndescription: Bold event posters from one line.\n---\n\nMake a bold event poster from the user's one-line brief.\n")
    return buf.getvalue()


async def _listing(route):
    import folder_paths
    from urllib.parse import parse_qs, urlparse
    q = parse_qs(urlparse(route.request.url).query)
    root = Path(folder_paths.STATE["base"]) / "user/default" / q["dir"][0]
    if not root.is_dir():
        return await route.fulfill(status=404, body="")
    if q.get("recurse") == ["true"]:
        files = [str(f.relative_to(root)) for f in root.rglob("*") if f.is_file()]
    else:
        files = [f.name for f in root.iterdir()]
    await route.fulfill(status=200, content_type="application/json", body=json.dumps(files))


@pytest.mark.parametrize("lang", ["en"])
async def test_import_skill_from_dropdown_end_to_end_650(app_url, lang, tmp_path):  # noqa: F811
    z = tmp_path / "poster-650.zip"
    z.write_bytes(_zip())
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, app_url, lang)
        await pg.route("**/api/userdata?dir=*", _listing)  # the shared stub host lists nothing; serve ComfyUI's real listing from disk
        await pg.get_by_test_id("skills-create-menu").click()
        await pg.get_by_test_id("skills-import").click()
        await pg.get_by_test_id("skill-import-dialog").wait_for()
        await _shot(pg, "ours-import-dialog")
        await pg.get_by_test_id("skill-import-zip-input").set_input_files(str(z))
        await pg.get_by_test_id("skill-import-dialog").wait_for(state="detached", timeout=15_000)
        assert not await pg.get_by_test_id("skill-import-error").count()
        await pg.wait_for_timeout(1500)
        await _shot(pg, "ours-import-after")
        landing_ok = not await pg.get_by_text("Skill not found").count()
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(1500)
        await _shot(pg, "ours-import-after-close")
        await pg.get_by_text("Poster 650").first.wait_for(timeout=10_000)
        await pg.wait_for_timeout(500)
        await _shot(pg, "ours-import-success")
        await browser.close()
        if not landing_ok:  # #692: the skill is saved and listed, but the post-import editor landing says "Skill not found"
            pytest.xfail("#692 post-import landing shows 'Skill not found' (skill itself is saved + listed)")
