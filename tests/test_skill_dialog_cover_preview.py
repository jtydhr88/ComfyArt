"""Dialog left: cover main-preview when examples/presetTiles empty; NEW19 examples stay []."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
SKILLS = (ROOT / "src/skills.ts").read_text()

NEW19 = [
    "taobao-product", "before-after", "anim-2d", "creator-identity", "product-website",
    "studio-model", "youtube-channel-banner", "ai-model", "product-to-packaging",
    "game-art", "portrait-studio", "premium-website", "animated-poster", "pose-fission",
    "live-promo-decor", "linkedin-banner", "logo-animation", "restaurant-website", "clothing-swap",
]


def test_cover_main_preview_hooks():
    assert "skillCover" in DLG
    assert 'data-testid="skill-run-cover-preview"' in DLG
    assert 'data-testid="skill-run-cover-stage"' in DLG
    assert 'data-testid="skill-run-cover-img"' in DLG
    assert 'data-left="cover"' in DLG
    # Dedicated hero — not SkillExamples with a fake single item
    assert "SkillExamples examples={[coverSrc" not in DLG
    assert "examples={[coverSrc" not in DLG
    # Still null when neither cover nor examples/tiles
    assert "if (!coverSrc) return null" in DLG


def test_new19_examples_still_empty_covers_pinned():
    a = SKILLS.index("export const BUILTIN_SKILLS")
    block = SKILLS[a:next(i for i in (SKILLS.find("\n])\n", a), SKILLS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    entries = {p.split("'", 1)[0]: p for p in parts}
    for sid in NEW19:
        e = entries[sid]
        assert "examples: []" in e, sid
        assert "featured: []" in e, sid
        head = e.split("inputs:", 1)[0]
        assert f"cover: cover643('{sid}')" in head, sid
