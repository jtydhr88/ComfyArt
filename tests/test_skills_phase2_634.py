"""#634 Phase2-S1: data contract — upgrade social + 14 NEW ids in BUILTIN_SKILLS (cut2), PRODUCT-LOCK-PHASE2.
$0 static reads; no network. Comments chain to #634 + PRODUCT-LOCK-PHASE2."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())

PHASE2_NEW = [
    "flash-cut-video", "style-transfer", "person-swap", "commerce-strategist", "lifestyle-scene",
    "naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce",
    "yingzao", "crt-interface", "crayon-sketch", "fabric-collage",
]
UNTOUCHED = ["interior", "custom-workflow"]
NEW_CATEGORY = {
    "flash-cut-video": "ads",
    "style-transfer": "branding",
    "person-swap": "ecommerce",
    "commerce-strategist": "ecommerce",
    "lifestyle-scene": "ecommerce",
    "naive-illustration": "social",
    "logo-abstract": "branding",
    "photo-split-poster": "ads",
    "ppt-visual": "website",
    "promo-ecommerce": "ecommerce",
    "yingzao": "social",
    "crt-interface": "social",
    "crayon-sketch": "social",
    "fabric-collage": "social",
}
TITLE_KEY = {
    "flash-cut-video": "skills.flashCutVideo",
    "style-transfer": "skills.styleTransfer",
    "person-swap": "skills.personSwap",
    "commerce-strategist": "skills.commerceStrategist",
    "lifestyle-scene": "skills.lifestyleScene",
    "naive-illustration": "skills.naiveIllustration",
    "logo-abstract": "skills.logoAbstract",
    "photo-split-poster": "skills.photoSplitPoster",
    "ppt-visual": "skills.pptVisual",
    "promo-ecommerce": "skills.promoEcommerce",
    "yingzao": "skills.yingzao",
    "crt-interface": "skills.crtInterface",
    "crayon-sketch": "skills.crayonSketch",
    "fabric-collage": "skills.fabricCollage",
}


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def test_phase2_ids_present_social_kept_untouched_and_no_skill_creator():
    ids = list(_entries())
    assert set(PHASE2_NEW) <= set(ids)
    assert "social" in ids
    assert all(u in ids for u in UNTOUCHED)
    assert len(ids) == 31  # 17 Phase1+untouched + 14 NEW
    assert "skill-creator" not in ids and "fashion-ugc" not in ids
    assert "PHASE2_NEW_SKILL_IDS" in SKILLS_TS
    assert "#634" in SKILLS_TS and "PRODUCT-LOCK-PHASE2" in SKILLS_TS
    assert "Fashion UGC" in SKILLS_TS


def test_new_skills_cut2_skeleton_categories():
    entries = _entries()
    for sid, cat in NEW_CATEGORY.items():
        e = entries[sid]
        assert f"category: '{cat}'" in e, sid
        assert "instructions:" in e and "inputs:" in e, sid
        assert "name: t(" in e, sid
        assert "presets:" in e, sid
        assert "examples: []" in e and "featured: []" in e, sid
        # S1: no washed cover/video pins yet (S4)
        head = e.split("inputs:", 1)[0]
        assert "cover:" not in head and "video:" not in head, sid
        assert "demo" not in e.lower() and "placeholder.webp" not in e, sid


def test_locale_titles_and_descriptions_for_new_ids():
    for sid, key in TITLE_KEY.items():
        assert ZH[key].strip() and EN[key].strip()
        assert "demo" not in ZH[key].lower() and "demo" not in EN[key].lower()
        assert ZH[f"skills.desc.{sid}"] and EN[f"skills.desc.{sid}"]
        assert ZH[f"skills.cat.{sid}"] and EN[f"skills.cat.{sid}"]
    assert ZH[TITLE_KEY["ppt-visual"]] == "高级感 PPT 视觉"
    assert EN[TITLE_KEY["ppt-visual"]] == "Premium PPT Visual"
    assert ZH[TITLE_KEY["flash-cut-video"]] == "截图闪剪视频"
    assert NEW_CATEGORY["ppt-visual"] == "website"


def test_no_lovart_string_in_src_skills():
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
