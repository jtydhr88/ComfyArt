"""#610 soft P1 — home category pills order + starter-card click (not prompt-fill)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "src/home/Home.tsx").read_text(encoding="utf-8")
CSS = (ROOT / "src/styles/home.css").read_text(encoding="utf-8")
EN = json.loads((ROOT / "src/locales/en.json").read_text(encoding="utf-8"))
ZH = json.loads((ROOT / "src/locales/zh.json").read_text(encoding="utf-8"))


def _quick_ids_in_source_order() -> list[str]:
    # Match QUICK entries in declaration order
    return re.findall(r"id: '(ecommerce|social|brand|creative|website)'", HOME)


def test_quick_order_ecommerce_first():
    ids = _quick_ids_in_source_order()
    assert ids[:5] == ["ecommerce", "social", "brand", "creative", "website"], ids[:5]


def test_locale_labels_order_keys():
    assert EN["home.quickEcommerce"] == "E-commerce"
    assert EN["home.quickSocial"] == "Social media"
    assert EN["home.quickBrand"] == "Brand"
    assert EN["home.quickCreative"] == "Creative"
    assert EN["home.quickWebsite"] == "Website"
    assert ZH["home.quickEcommerce"] == "电商"
    assert ZH["home.quickSocial"] == "社交媒体"
    assert ZH["home.quickBrand"] == "品牌"
    assert ZH["home.quickCreative"] == "创意"
    assert ZH["home.quickWebsite"] == "网站"


def test_retire_prompt_fill_primary():
    # Pill click must open starter, not setText(prompt)
    assert "setStarter(q.id)" in HOME
    assert "setText(prompt)" not in HOME
    assert "home.quickSocialPrompt" not in HOME  # retired from QUICK wiring
    assert "home-v3-starter-back" in HOME
    assert "ca-home-starter" in HOME
    assert "aria-pressed={starter === q.id}" in HOME


def test_phase1_suggestion_skill_ids():
    # ecommerce → product / packaging / multi-angle
    assert "{ skillId: 'product-tvc-advertisement-generator'" in HOME
    assert "{ skillId: 'packaging-design-director'" in HOME
    assert "{ skillId: 'universal-multi-angle-grid'" in HOME
    # social → social / thumbnail (+ soft alt social)
    assert HOME.count("{ skillId: 'rednote-cover-maker'") >= 2
    assert "{ skillId: 'cover-design-director'" in HOME
    # brand → brand / logo-material
    assert "{ skillId: 'logo-material-explorer'" in HOME
    # creative pick 3 from phase1 ads family
    assert "{ skillId: 'poster-differentiated-compiler'" in HOME
    assert "{ skillId: 'banner-design-director'" in HOME
    assert "{ skillId: 'meta-ads-creative-director'" in HOME
    # website → mobile-ui / web-product
    assert "{ skillId: 'mobile-app-visual-design'" in HOME
    assert "{ skillId: 'web-product-visual-design'" in HOME
    # character stays forYou-only — not in starter suggests
    assert "skillId: 'character-sheet-design'" not in HOME


def test_breakdown_not_in_five_pill_row():
    # 拆解图片 must not sit inside the 1:1 five-pill QUICK row
    assert "home.breakdown" not in HOME
    assert "breakDown" not in HOME


def test_tools_segregation_untouched_markers():
    # #537/#540 cards still present; this card must not rewrite tool ids
    for tid in ("cutout", "extend", "upscale", "inpaint", "mockup"):
        assert f"id: '{tid}'" in HOME or f'id: "{tid}"' in HOME or f"home-tool-card-{tid}" in HOME
    assert "HOME_TOOL_CARDS" in HOME
    assert "MORE_HOME_TOOLS" in HOME


def test_starter_css_and_chip_chrome():
    assert ".ca-landing__starter" in CSS
    assert ".ca-landing__starter-back" in CSS
    assert re.search(r"\.ca-landing__chip\s*\{[^}]*height:\s*32px", CSS)
    assert "border-radius: 9999px" in CSS


def test_no_competitor_brand_in_touched_src():
    blob = HOME + CSS
    assert "Lovart" not in blob
    assert "lovart" not in blob


def test_starter_locale_keys_present():
    for key in (
        "home.starter.product",
        "home.starter.packaging",
        "home.starter.multiAngle",
        "home.starter.social",
        "home.starter.thumbnail",
        "home.starter.socialAlt",
        "home.starter.brand",
        "home.starter.logoMaterial",
        "home.starter.brandAlt",
        "home.starter.poster",
        "home.starter.banner",
        "home.starter.metaAds",
        "home.starter.mobileUi",
        "home.starter.webProduct",
        "home.starter.webProductAlt",
        "home.starterCategories",
    ):
        assert key in EN and key in ZH, key
