"""#594 Phase1 wash static: new6 cover/featured/examples pins + dual-fit contain; #623 hover video; no competitor CDN.
$0 static reads; no network."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
SKILLS = (ROOT / "src/home/Skills.tsx").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()

PHASE1_NEW = ["universal-multi-angle-grid", "logo-material-explorer", "meta-ads-creative-director", "mobile-app-visual-design", "web-product-visual-design", "marketing-campaign-generator"]
WASH_594 = "cc76d743d416c3d9a9a6852d811a7a80caf40319"


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a:next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def test_wash_594_pin_and_paths():
    assert f"const WASH_594 = '{WASH_594}'" in SKILLS_TS
    assert "494/covers-v4" in SKILLS_TS and "580/featured-v2" in SKILLS_TS
    assert "594/wash/" in SKILLS_TS and "ex594" in SKILLS_TS
    assert "WASH_623_NEW6_VIDEO" in SKILLS_TS
    assert "d03ea7938877d084c201a94ef51f943dd0e061b9" in SKILLS_TS
    assert "video594" in SKILLS_TS and "594/wash/videos/" in SKILLS_TS
    for sid in PHASE1_NEW:
        e = _entries()[sid]
        head = e.split("inputs:", 1)[0]
        assert f"cover: cover('{sid}')" in head
        assert f"featured: feedCovers('{sid}')" in head
        assert f"examples: ex594('{sid}', [1, 2{'' if sid == 'logo-material-explorer' else ', 3, 4'}])" in head  # #748: logo-material left = 1 video + 2 images
        assert "quickStartCoverFit: 'contain'" in head
        assert f"video: video594('{sid}')" in head  # #623
        assert "lovart" not in head.lower()


def test_dual_fit_skills_wall_and_home():
    assert "skillQuickStartCoverFit" in SKILLS and 'data-fit={skillQuickStartCoverFit(skill)}' in SKILLS
    assert '.ca-swall__cover[data-fit="contain"]' in CSS
    assert '.ca-skillcard__cover[data-fit="contain"]' in CSS
    assert "object-fit: contain" in CSS


def test_no_competitor_cdn_or_name_in_src_skills():
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
    assert "cdn.lovart" not in SKILLS_TS.lower()
