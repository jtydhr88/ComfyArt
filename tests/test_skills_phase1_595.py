"""#595 Phase1-S5 mount: home + Skills Explore hang Phase1 15 (hot order), website chip, no demo/dupes.
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
UNTOUCHED = ["interior"]  # custom-workflow removed (no Lovart card)
PHASE1_NEW = ["multi-angle", "logo-material", "meta-ads", "mobile-ui", "web-product", "marketing-campaign"]


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:SKILLS_TS.index("\n])\n", a)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def _builtin_ids_in_source_order() -> list[str]:
    """Ids as written inside orderBuiltins([...]) before sort — used only as a presence check."""
    return list(_entries())


def test_phase1_hot_order_constant_and_wrapper():
    assert "export const PHASE1_SKILL_IDS" in SKILLS_TS
    assert "function orderBuiltins" in SKILLS_TS
    assert "orderBuiltins([" in SKILLS_TS
    # Literal order in the const matches product-lock hot uses (unique Phase1).
    m = re.search(r"export const PHASE1_SKILL_IDS = \[([^\]]+)\] as const", SKILLS_TS, re.S)
    assert m, "PHASE1_SKILL_IDS literal missing"
    ids = re.findall(r"'([^']+)'", m.group(1))
    assert ids == PHASE1
    assert len(ids) == 15
    assert len(set(ids)) == 15


def test_builtins_mount_phase1_plus_untouched_no_voided_dupes():
    ids = _builtin_ids_in_source_order()
    assert set(PHASE1) <= set(ids)
    assert all(u in ids for u in UNTOUCHED)
    assert len(ids) >= 17  # #634 Phase2-S1 adds 14 NEW
    # deferred .art ids now land in Phase2 — presence OK


def test_website_chip_source_and_home_skills_same_data():
    # website categories on the two NEW website skills
    entries = _entries()
    assert "category: 'website'" in entries["mobile-ui"]
    assert "category: 'website'" in entries["web-product"]
    assert "SKILL_CATEGORY_ORDER" in SKILLS_TS and "'website'" in SKILLS_TS
    # Home + Skills Explore both pull skillChips / matchesSkillChip / loadSkills — same source
    assert "skillChips(" in HOME and "matchesSkillChip(" in HOME
    assert "skillChips(" in SKILLS_PAGE and "matchesSkillChip(" in SKILLS_PAGE
    assert "loadSkills(" in HOME and "loadSkills(" in SKILLS_PAGE
    assert "skillFeaturedCases(" in HOME
    assert "HOME_SKILL_ROW" in HOME


def test_dialog_carousel_inputs_agent_handoff():
    assert "SkillExamples" in DIALOG
    assert "skill-run-examples" in (ROOT / "src/ui/SkillExamples.tsx").read_text()
    assert "skillRunParams" in DIALOG
    assert "mode: 'agent'" in SKILLS_TS
    assert "newProject(" in DIALOG or "skillRunParams" in DIALOG


def test_phase1_media_and_no_demo_placeholder():
    entries = _entries()
    for sid in PHASE1:
        e = entries[sid]
        head = e.split("inputs:", 1)[0]
        assert "cover: cover(" in head, sid
        assert "featured: feedCovers(" in head, sid
        assert "demo" not in e.lower(), sid
        assert "placeholder.webp" not in e, sid
        assert "lovart" not in e.lower(), sid
    for sid in PHASE1_NEW:
        e = entries[sid]
        assert "examples: ex594(" in e, sid
        assert "quickStartCoverFit: 'contain'" in e, sid


def test_no_lovart_string_in_src_skills():
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
