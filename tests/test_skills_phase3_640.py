"""#640 Phase3-S1: data contract — upgrade thumbnail + 19 NEW ids in BUILTIN_SKILLS (cut2).
PRODUCT-LOCK-PHASE3 + PHASE3-HARDEN-DIFF. Skill Creator → #650. $0 static reads; no network."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())

PHASE3_NEW = [
    "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website",
    "studio-model", "youtube-channel-banner", "ai-model", "product-to-packaging",
    "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission",
    "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap",
]
DROPPED_13 = [
    "app-listing-kit", "ip-logo", "magazine-postcard", "poster", "talking-collage", "brand",
    "anime-official-site", "cinematic-snapshot", "zhixian-poster", "cartoon-ip-extend",
    "culture-creative", "new-chinese-mobile", "portfolio-site",
]
# poster/brand remain as Phase1 ids — "dropped" means do not re-land as Phase3 NEW/upgrade slots.
DROPPED_MUST_ABSENT = [
    "app-listing-kit", "ip-logo", "magazine-postcard", "talking-collage",
    "anime-official-site", "cinematic-snapshot", "zhixian-poster", "cartoon-ip-extend",
    "culture-creative", "new-chinese-mobile", "portfolio-site",
]
UNTOUCHED = ["interior", "custom-workflow"]
NEW_CATEGORY = {
    "taobao-product": "ecommerce",
    "before-after": "ads",
    "anim-2d": "ads",
    "creator-identity": "branding",
    "product-website": "website",
    "studio-model": "ecommerce",
    "youtube-channel-banner": "social",
    "ai-model": "ecommerce",
    "product-to-packaging": "ecommerce",
    "game-art": "ads",
    "portrait-studio": "social",
    "premium-website": "website",
    "animated-poster": "ads",
    "pose-fission": "ecommerce",
    "live-promo-decor": "ecommerce",
    "linkedin-banner": "social",
    "logo-animation": "branding",
    "restaurant-website": "website",
    "clothing-swap": "ecommerce",
}
TITLE_KEY = {
    "taobao-product": "skills.taobaoProduct",
    "before-after": "skills.beforeAfter",
    "anim-2d": "skills.anim2d",
    "creator-identity": "skills.creatorIdentity",
    "product-website": "skills.productWebsite",
    "studio-model": "skills.studioModel",
    "youtube-channel-banner": "skills.youtubeChannelBanner",
    "ai-model": "skills.aiModel",
    "product-to-packaging": "skills.productToPackaging",
    "game-art": "skills.gameArt",
    "portrait-studio": "skills.portraitStudio",
    "premium-website": "skills.premiumWebsite",
    "animated-poster": "skills.animatedPoster",
    "pose-fission": "skills.poseFission",
    "live-promo-decor": "skills.livePromoDecor",
    "linkedin-banner": "skills.linkedinBanner",
    "logo-animation": "skills.logoAnimation",
    "restaurant-website": "skills.restaurantWebsite",
    "clothing-swap": "skills.clothingSwap",
}
WEBSITE_NEW = ["product-website", "premium-website", "restaurant-website"]


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def test_phase3_ids_match_hard_lock_thumbnail_kept_untouched_no_dropped_no_skill_creator():
    ids = list(_entries())
    assert set(PHASE3_NEW) <= set(ids)
    assert "thumbnail" in ids
    assert all(u in ids for u in UNTOUCHED)
    assert len(ids) == 50  # 31 prior + 19 NEW
    assert "PHASE3_NEW_SKILL_IDS" in SKILLS_TS
    assert "#640" in SKILLS_TS and "PRODUCT-LOCK-PHASE3" in SKILLS_TS and "PHASE3-HARDEN-DIFF" in SKILLS_TS
    assert "skill-creator" not in ids
    for d in DROPPED_MUST_ABSENT:
        assert d not in ids, d
    # Dropped Phase3 board ids must not appear as Phase3 NEW constants
    for d in DROPPED_13:
        if d in ("poster", "brand"):
            continue  # Phase1 keep
        assert f"'{d}'" not in SKILLS_TS.split("PHASE3_NEW_SKILL_IDS", 1)[1].split("] as const", 1)[0]


def test_new_skills_cut2_skeleton_categories_and_website_chip_sources():
    entries = _entries()
    for sid, cat in NEW_CATEGORY.items():
        e = entries[sid]
        assert f"category: '{cat}'" in e, sid
        assert "instructions:" in e and "inputs:" in e, sid
        assert "name: t(" in e, sid
        assert "presets:" in e, sid
        assert "examples: []" in e and "featured: []" in e, sid
        head = e.split("inputs:", 1)[0]
        assert f"cover: cover643('{sid}')" in head, sid  # #643 NEW19 cover pins
        assert "video:" not in head, sid
        assert "demo" not in e.lower() and "placeholder.webp" not in e, sid
    for sid in WEBSITE_NEW:
        assert "category: 'website'" in entries[sid]
    # upgrade thumbnail still social + present
    assert "category: 'social'" in entries["thumbnail"]
    assert ("#640 Phase3-S1 upgrade slot" in SKILLS_TS) or ("#641 Phase3-S2" in SKILLS_TS and "thumbnail" in SKILLS_TS)


def test_locale_titles_descriptions_categories_for_new_ids():
    for sid, key in TITLE_KEY.items():
        assert ZH[key].strip() and EN[key].strip()
        assert "demo" not in ZH[key].lower() and "demo" not in EN[key].lower()
        assert ZH[f"skills.desc.{sid}"] and EN[f"skills.desc.{sid}"]
        assert ZH[f"skills.cat.{sid}"] and EN[f"skills.cat.{sid}"]
    assert ZH[TITLE_KEY["taobao-product"]] == "淘宝商品视觉"
    assert EN[TITLE_KEY["taobao-product"]] == "Taobao Product Visuals"
    assert ZH[TITLE_KEY["product-website"]] == "产品网站设计师"
    assert NEW_CATEGORY["restaurant-website"] == "website"


def test_no_lovart_string_in_src_skills():
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
