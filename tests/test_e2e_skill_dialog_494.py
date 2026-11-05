"""#494-2 e2e (mock only, $0; NOT run until GO): card / title / hover try → the skill's own left/right dialog,
presets, required gating, handoff URL, Personal groups, old personal skill keeps main's direct start."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401  (fixtures)
from test_e2e_skill_cards_494 import _open

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_dialog_from_data_and_handoff(app_url, lang):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, lang)
        # #569: poster is an effect skill (upload + note, no presets); preset/required handoff runs on brand.
        await pg.locator('[data-skill="poster-differentiated-compiler"] .ca-swall__cover').click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        assert await dlg.get_attribute("data-skill") == "poster-differentiated-compiler"
        keys = await dlg.get_by_test_id("skill-run-field").evaluate_all("fs => fs.map(f => f.dataset.key)")
        assert keys == ["user_image", "user_requirement"]  # #748 Final example form (raw)
        assert await pg.get_by_test_id("skill-run-preset").count() == 0
        assert await pg.get_by_test_id("skill-run-go").evaluate("b => !b.disabled")  # #748: required raw fields → aria-disabled look, still clickable
        assert await pg.get_by_test_id("skill-run-go").get_attribute("aria-disabled") == "true"
        await pg.keyboard.press("Escape")
        await pg.locator('[data-skill="brand-identity-director"] .ca-swall__cover').click()
        dlg = pg.get_by_test_id("skill-run-dialog")
        await dlg.wait_for()
        assert await dlg.get_attribute("data-skill") == "brand-identity-director"
        assert await dlg.locator(".ca-skillrun__left").count() == 1
        assert await dlg.locator(".ca-skillrun__right").count() == 1
        keys = await dlg.get_by_test_id("skill-run-field").evaluate_all("fs => fs.map(f => f.dataset.key)")
        assert keys == ["brand_info", "subject_image", "visual_direction"]  # #748 Final raw: brand template[0] form
        assert await pg.get_by_test_id("skill-run-preset").count() == 6
        go = pg.get_by_test_id("skill-run-go")
        assert await go.get_attribute("aria-disabled") == "true"  # #748 required brand_info empty
        await pg.locator('[data-testid="skill-run-field"][data-key="brand_info"]').fill("Autumn launch")
        await pg.get_by_test_id("skill-run-preset").nth(1).click()
        assert await pg.get_by_test_id("skill-run-current").inner_text()
        await go.click()
        await pg.wait_for_url(re.compile(r"[?&]skill=brand-identity-director"), timeout=10_000)
        assert "preset=handmade" in pg.url and "mode=agent" in pg.url
        await browser.close()


async def test_title_and_hover_try_open_same_dialog(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh")
        card = pg.locator('[data-skill="poster-differentiated-compiler"]')
        await card.hover()
        await card.get_by_test_id("skills-card-try").click()
        assert await pg.get_by_test_id("skill-run-dialog").get_attribute("data-skill") == "poster-differentiated-compiler"
        await pg.keyboard.press("Escape")
        await card.locator(".ca-swall__title").click()
        assert await pg.get_by_test_id("skill-run-dialog").get_attribute("data-skill") == "poster-differentiated-compiler"
        await browser.close()


async def test_other_skill_has_other_fields(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "en")
        assert await pg.locator('[data-skill="custom-workflow"]').count() == 0  # card removed (no Lovart card)
        await pg.locator('[data-skill="product-tvc-advertisement-generator"] .ca-swall__cover').click()
        keys = await pg.get_by_test_id("skill-run-field").evaluate_all("fs => fs.map(f => f.dataset.key)")
        assert keys and "note" not in keys  # product has its own fields, not poster's (#687: brand now = Upload + Additional)
        await browser.close()


async def test_detail_opens_edit_form(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh")
        await pg.locator('[data-skill="poster-differentiated-compiler"] .ca-swall__cover').click()
        # #687 P0: builtin poster no longer exposes 「详情」 → editor (SKILL.md).
        await pg.get_by_test_id("skill-run-dialog").wait_for()
        assert await pg.get_by_test_id("skill-run-detail").count() == 0
        assert await pg.get_by_test_id("skill-form").count() == 0
        await browser.close()


async def test_builtin_has_no_detail_editor_687(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        for lang in ("zh", "en"):
            browser, pg = await _open(p, app_url, lang)
            for sid in ("poster-differentiated-compiler", "product-tvc-advertisement-generator", "packaging-design-director"):
                await pg.locator(f'[data-skill="{sid}"] .ca-swall__cover').click()
                await pg.get_by_test_id("skill-run-dialog").wait_for()
                assert await pg.get_by_test_id("skill-run-detail").count() == 0
                assert await pg.get_by_test_id("skill-form").count() == 0
                await pg.keyboard.press("Escape")
            await browser.close()


async def test_personal_groups_and_old_skill_starts_directly(app_url):  # noqa: F811
    async with pw.async_playwright() as p:
        browser, pg = await _open(p, app_url, "zh")
        await pg.get_by_test_id("skills-tab-personal").click()
        assert await pg.get_by_test_id("skills-group-yours").inner_text()
        assert "你创建的" in await pg.get_by_test_id("skills-group-yours").inner_text()
        assert "Loomi 创建的" in await pg.get_by_test_id("skills-group-loomi").inner_text()
        assert "暂无自动总结的技能" in await pg.get_by_test_id("skills-empty-loomi").inner_text()
        await pg.locator('[data-skill="old-skill"]').click()
        await pg.wait_for_url(re.compile(r"[?&]skill=old-skill"), timeout=10_000)
        assert await pg.get_by_test_id("skill-run-dialog").count() == 0
        await browser.close()
