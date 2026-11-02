"""#593 Phase1-S3: new-6 production instructions+presets; dual-column CTA Start making; #594 wash pins land on tip.
$0 static reads; no network."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
EXAMPLES = (ROOT / "src/ui/SkillExamples.tsx").read_text()
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())

PHASE1_NEW = ["multi-angle", "logo-material", "meta-ads", "mobile-ui", "web-product", "marketing-campaign"]
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


def test_new6_production_instructions_and_presets():
    entries = _entries()
    assert len(entries) >= 17  # #634 +14 NEW
    for sid, cat in NEW_CATEGORY.items():
        e = entries[sid]
        assert f"category: '{cat}'" in e, sid
        head, _, rest = e.partition("inputs:")
        assert "cover: cover(" in head and "featured: feedCovers(" in head, sid
        assert f"video: video594('{sid}')" in head, sid  # #623 hover video wired
        assert "quickStartCoverFit: 'contain'" in head and "examples: ex594(" in head, sid
        assert "presets:" in head, sid
        body = head.split("presets:", 1)[1]
        n = body.count("P(")
        assert n >= 4, (sid, n)
        instr = re.search(r"instructions: '((?:\\'|[^'])*)'", e)
        assert instr, sid
        steps = instr.group(1)
        assert "\\n1)" in steps and "\\n5)" in steps, sid
        assert "Template:" not in steps, sid  # keep Template:/Style: in preset prompts only
        assert "demo" not in steps.lower() and "Lovart" not in steps and "lovart" not in steps


def test_dual_column_dialog_start_making_and_numbered_filmstrip():
    assert ".ca-skillrun__left" in CSS and ".ca-skillrun__right" in CSS
    assert 'data-testid="skill-run-go"' in DLG
    assert ZH["skillRun.start"] == "开始制作"
    assert EN["skillRun.start"] == "Start making"
    # #601: header key distinct from CTA; filmstrip zero-padded
    assert ZH["skillRun.header"] == "开始创作" and EN["skillRun.header"] == "Start Creating"
    assert "skillRun.header" in DLG and "filmstripIndexLabel" in EXAMPLES and "filmstripIndexLabel" in SKILLS_TS
    assert "ca-skillrun__thumbnum" in EXAMPLES and "data-index" in EXAMPLES
    assert ".ca-skillrun__thumbnum" in CSS
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
    assert "Lovart" not in DLG and "Lovart" not in EXAMPLES


def test_website_chip_still_lit():
    assert "category: 'website'" in SKILLS_TS
    for sid in ("mobile-ui", "web-product"):
        assert f"id: '{sid}'" in SKILLS_TS
