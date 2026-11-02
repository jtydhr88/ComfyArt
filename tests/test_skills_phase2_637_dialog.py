"""#637 — B NEW5 SkillRunDialog left column is Examples-only (gold isomorphic), not 「模板」 grid."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
EX = (ROOT / "src/ui/SkillExamples.tsx").read_text()


def test_examples_only_left_no_cover_fallback_template_grid():
    assert "presetTiles" in DLG
    assert "p.image || p.video" in DLG
    assert 'data-left={examples.length ? (presetTiles.length ? \'both\' : \'examples\') : \'templates\'}' in DLG
    # #636 product lock: Examples-only does not render 「当前模板」 native select
    assert "skill-run-preset-select" not in DLG
    assert "if (!pickOnLeft) return null" in DLG
    assert "<SkillExamples examples={skill.examples} />" in DLG
    assert "Lovart" not in DLG and "lovart" not in DLG
    assert "Lovart" not in EX and "lovart" not in EX


def test_skill_examples_data_count_drives_shape():
    assert 'data-count={examples.length}' in EX
    assert "examples.length > 1" in EX  # filmstrip only when carousel
