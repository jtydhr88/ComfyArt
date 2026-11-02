"""#638 Phase2-S5 Soft mount: home + Skills hang Phase2 A+B (Soft order); C/D deferred; #490 HOLD.
$0 static reads; no network."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
HOME = (ROOT / "src/home/Home.tsx").read_text()
SKILLS_PAGE = (ROOT / "src/home/Skills.tsx").read_text()
DIALOG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()

PHASE1 = [
    "product", "multi-angle", "brand", "character", "logo-material", "packaging",
    "motion", "meta-ads", "poster", "thumbnail", "mobile-ui", "social",
    "marketing-campaign", "web-product", "banner",
]
# Soft order slots 1–6 (PRODUCT-LOCK-PHASE2): A social + B NEW5
PHASE2_MOUNT = [
    "flash-cut-video", "style-transfer", "person-swap", "social",
    "commerce-strategist", "lifestyle-scene",
]
PHASE2_B = [
    "flash-cut-video", "style-transfer", "person-swap",
    "commerce-strategist", "lifestyle-scene",
]
PHASE2_DEFERRED_C = [
    "naive-illustration", "logo-abstract", "photo-split-poster", "ppt-visual", "promo-ecommerce",
]
PHASE2_DEFERRED_D = ["yingzao", "crt-interface", "crayon-sketch", "fabric-collage"]
UNTOUCHED = ["interior", "custom-workflow"]


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def _const_ids(name: str) -> list[str]:
    m = re.search(rf"export const {name} = \[([^\]]+)\] as const", SKILLS_TS, re.S)
    assert m, f"{name} literal missing"
    return re.findall(r"'([^']+)'", m.group(1))


def test_phase2_soft_mount_constants():
    assert _const_ids("PHASE2_SKILL_IDS") == PHASE2_MOUNT
    assert len(PHASE2_MOUNT) == 6 and len(set(PHASE2_MOUNT)) == 6
    assert "social" in PHASE2_MOUNT and "fashion-ugc" not in PHASE2_MOUNT
    deferred = _const_ids("PHASE2_DEFERRED_SKILL_IDS")
    assert deferred == PHASE2_DEFERRED_C + PHASE2_DEFERRED_D
    # C/D must not be in Soft mount list
    assert not (set(PHASE2_DEFERRED_C + PHASE2_DEFERRED_D) & set(PHASE2_MOUNT) - {"social"})
    assert "ppt-visual" not in PHASE2_MOUNT  # C HOLD
    assert "#638" in SKILLS_TS and "PRODUCT-LOCK-PHASE2" in SKILLS_TS
    assert "#490" in SKILLS_TS and "HOLD" in SKILLS_TS


def test_order_builtins_phase1_then_phase2_b_then_deferred():
    assert "function orderBuiltins" in SKILLS_TS
    assert "PHASE2_SKILL_IDS" in SKILLS_TS and "PHASE2_DEFERRED_SKILL_IDS" in SKILLS_TS
    # Simulate order: Phase1 → B NEW5 Soft → deferred → untouched
    ids = list(_entries())
    # Source presence
    assert set(PHASE1) <= set(ids)
    assert set(PHASE2_B) <= set(ids)
    assert set(PHASE2_DEFERRED_C + PHASE2_DEFERRED_D) <= set(ids)
    assert all(u in ids for u in UNTOUCHED)
    assert len(ids) == 31
    # Runtime order is orderBuiltins output — assert the exported const lists encode Soft order
    assert _const_ids("PHASE1_SKILL_IDS") == PHASE1
    assert _const_ids("PHASE2_SKILL_IDS") == PHASE2_MOUNT
    # No duplicate mount of social as a second id
    assert ids.count("social") == 1


def test_b_washed_mounted_deferred_still_empty_assets():
    entries = _entries()
    for sid in PHASE2_B:
        e = entries[sid]
        head = e.split("inputs:", 1)[0]
        assert "cover: cover637(" in head, sid
        assert "featured: feat637(" in e or "featured:" in head, sid
        assert "demo" not in e.lower() and "placeholder.webp" not in e, sid
        assert "lovart" not in e.lower(), sid
    for sid in PHASE2_DEFERRED_C + PHASE2_DEFERRED_D:
        e = entries[sid]
        head = e.split("inputs:", 1)[0]
        assert "examples: []" in e and "featured: []" in e, sid
        assert "cover637" not in head, sid


def test_home_skills_same_source_and_chips():
    assert "skillChips(" in HOME and "matchesSkillChip(" in HOME
    assert "skillChips(" in SKILLS_PAGE and "matchesSkillChip(" in SKILLS_PAGE
    assert "loadSkills(" in HOME and "loadSkills(" in SKILLS_PAGE
    assert "skillFeaturedCases(" in HOME
    assert "HOME_SKILL_ROW" in HOME
    # website chip source: Phase1 website skills (ppt-visual C HOLD — may stay out of mount)
    entries = _entries()
    assert "category: 'website'" in entries["mobile-ui"]
    assert "category: 'website'" in entries["web-product"]
    assert "category: 'website'" in entries["ppt-visual"]  # data present but deferred
    assert "'website'" in SKILLS_TS


def test_dialog_agent_handoff_and_social_fashion_ugc_regression():
    assert "mode: 'agent'" in SKILLS_TS
    assert "skillRunParams" in DIALOG
    social = _entries()["social"]
    presets = re.findall(r"\bP\('([^']+)'", social)
    assert "ugc-feed" in presets and "ugc-story" in presets
    assert "Fashion UGC" in social or "fashion UGC" in social.lower()
    assert "candid" in social.lower() or "off-duty" in social.lower()
    # commerce-strategist text-required path for e2e dialog→Agent
    assert "sellPoints" in _entries()["commerce-strategist"]


def test_no_lovart_string_in_src_skills():
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
    src = ROOT / "src"
    bad = []
    for p in src.rglob("*"):
        if p.suffix not in {".ts", ".tsx", ".js", ".jsx", ".css", ".json"}:
            continue
        t = p.read_text(errors="ignore")
        if "Lovart" in t or re.search(r"(?i)\blovart\b", t):
            bad.append(str(p.relative_to(ROOT)))
    assert not bad, bad
