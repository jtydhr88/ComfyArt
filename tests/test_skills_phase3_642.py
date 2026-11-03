"""#642 Phase3-S3: NEW19 full copy + dialog contract (scaffold).
Media wash stays #643. Skill Creator stays #650. $0 static reads; no network."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
DIALOG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
NOTES = (ROOT / "docs/design/642/78/NOTES.md").read_text()

PHASE3_NEW = [
    "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website",
    "studio-model", "youtube-channel-banner", "ai-model", "product-to-packaging",
    "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission",
    "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap",
]
DROPPED_MUST_ABSENT = [
    "app-listing-kit", "ip-logo", "magazine-postcard", "talking-collage",
    "anime-official-site", "cinematic-snapshot", "zhixian-poster", "cartoon-ip-extend",
    "culture-creative", "new-chinese-mobile", "portfolio-site",
]


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def _instructions(entry: str) -> str:
    m = re.search(r"instructions: ((?:'([^']*)')|(?:`([^`]*)`))", entry)
    assert m, entry[:80]
    return m.group(2) if m.group(2) is not None else m.group(3)


def test_notes_and_s3_marker():
    assert "#642" in NOTES and "Phase3-S3" in NOTES
    assert "#643" in NOTES and "#650" in NOTES
    assert "#642" in SKILLS_TS and "Phase3-S3" in SKILLS_TS


def test_new19_present_production_copy_dialog_inputs():
    entries = _entries()
    for sid in PHASE3_NEW:
        e = entries[sid]
        instr = _instructions(e)
        low = instr.lower()
        assert "you are a production" in low, sid
        assert "lovart" not in low, sid
        assert "demo" not in low, sid
        assert "inputs:" in e, sid
        assert "presets:" in e, sid
        assert len(re.findall(r"\bP\('", e)) >= 2, sid
        # S3 still allows empty media until #643
        assert "examples: []" in e and "featured: []" in e, sid
        head = e.split("inputs:", 1)[0]
        assert "cover:" not in head and "video:" not in head, sid


def test_no_dropped_ids_no_skill_creator_slot():
    ids = set(_entries())
    for d in DROPPED_MUST_ABSENT:
        assert d not in ids, d
    assert "skill-creator" not in ids
    assert "custom-workflow" in ids  # untouched; not an upgrade target


def test_dialog_shell_hooks_shared():
    for tid in (
        'data-testid="skill-run-modal"',
        'data-testid="skill-run-dialog"',
        'data-testid="skill-run-head"',
        'data-testid="skill-run-go"',
        'data-testid="skill-run-field-error"',
    ):
        assert tid in DIALOG
    assert "missingInputs" in DIALOG and "skillRunParams" in DIALOG


def test_no_lovart_string_under_src_skills_dialog():
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
    assert "Lovart" not in DIALOG and "lovart" not in DIALOG


def test_gold_status_stubs_exist():
    for sid in PHASE3_NEW:
        p = ROOT / f"docs/design/642/78/gold/{sid}/STATUS.txt"
        assert p.is_file(), sid
        assert f"id={sid}" in p.read_text()
