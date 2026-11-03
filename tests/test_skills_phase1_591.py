"""#591 Phase1-S1: hot-set data contract — 9 upgrade + 6 new ids in BUILTIN_SKILLS (cut2), website chip lit.
$0 static reads; no network."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())

PHASE1_UPGRADE = ["brand", "packaging", "poster", "product", "character", "social", "motion", "banner", "thumbnail"]
PHASE1_NEW = ["multi-angle", "logo-material", "meta-ads", "mobile-ui", "web-product", "marketing-campaign"]
PHASE1 = PHASE1_UPGRADE + PHASE1_NEW
UNTOUCHED = ["interior"]  # custom-workflow removed (no Lovart card)
TITLE_KEY = {
    "multi-angle": "skills.multiAngleImageGenerator",
    "logo-material": "skills.logoMaterialExplorer",
    "meta-ads": "skills.metaAdsCreative",
    "mobile-ui": "skills.mobileAppVisualDesign",
    "web-product": "skills.webProductVisualDesign",
    "marketing-campaign": "skills.marketingCampaignGenerator",
}
NEW_CATEGORY = {
    "multi-angle": "ecommerce",
    "logo-material": "branding",
    "meta-ads": "ads",
    "mobile-ui": "website",
    "web-product": "website",
    "marketing-campaign": "ads",
}


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def test_phase1_ids_present_and_untouched_kept():
    ids = list(_entries())
    assert set(PHASE1) <= set(ids)
    assert all(u in ids for u in UNTOUCHED)
    assert len(ids) >= 17
    # #634 Phase2 reclaims the deferred .art ids — no longer voided


def test_new_skills_cut2_skeleton_and_website_categories():
    entries = _entries()
    for sid, cat in NEW_CATEGORY.items():
        e = entries[sid]
        assert f"category: '{cat}'" in e, sid
        assert "instructions:" in e and "inputs:" in e, sid
        assert "name: t(" in e, sid
        # #594 wash pins — cover + featured; no hover video (#575)
        head = e.split("inputs:", 1)[0]
        assert "cover: cover(" in head and "featured: feedCovers(" in head, sid
        assert "video:" not in head, sid
        assert "quickStartCoverFit: 'contain'" in head, sid
        assert "examples: ex594(" in head, sid


def test_locale_titles_and_descriptions_for_new_ids():
    for sid, key in TITLE_KEY.items():
        assert ZH[key].strip() and EN[key].strip()
        assert "demo" not in ZH[key].lower() and "demo" not in EN[key].lower()
        assert ZH[f"skills.desc.{sid}"] and EN[f"skills.desc.{sid}"]
        assert ZH[f"skills.cat.{sid}"] and EN[f"skills.cat.{sid}"]
    assert ZH[TITLE_KEY["multi-angle"]] == "多角度图像生成器"
    assert EN[TITLE_KEY["multi-angle"]] == "Multi-Angle Image Generator"
    assert EN[TITLE_KEY["mobile-ui"]] == "Mobile APP Visual Design"
    assert EN[TITLE_KEY["web-product"]] == "Web Product Visual Design"


def test_no_lovart_string_in_src_skills():
    # Gold UX is lovart.ai in docs/PR only — never the competitor string inside src.
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
