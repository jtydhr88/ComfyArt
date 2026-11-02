"""#636 Phase2-S3 C deferred5 soft wash — hardMax left-column layouts from c5-nearmiss meta.
$0 static reads; no network. Product remap: logo carousel11; photo/ppt still1; promo/naive carousel4."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()

WASH_636 = "5ccfdf0f481bbcbb3392516dba75f1ec3bda3ab6"
PHASE2_C = [
    "naive-illustration",
    "logo-abstract",
    "photo-split-poster",
    "ppt-visual",
    "promo-ecommerce",
]
HARD_MAX = {
    "logo-abstract": 11,          # examples-carousel hardMax11
    "photo-split-poster": 1,      # examples-single-still
    "ppt-visual": 1,              # examples-single-still
    "promo-ecommerce": 4,         # examples-carousel4
    "naive-illustration": 4,      # examples-carousel4 (near=2qapfgd34fsw)
}
FEAT_MIN = {
    "logo-abstract": 5,
    "photo-split-poster": 3,
    "ppt-visual": 3,
    "promo-ecommerce": 5,
    "naive-illustration": 5,
}


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a : next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def test_wash_636_pin_and_helpers():
    assert f"const WASH_636 = '{WASH_636}'" in SKILLS_TS
    for h in ("cover636", "ex636", "feat636"):
        assert f"const {h}" in SKILLS_TS or f"{h} =" in SKILLS_TS or f"{h}(" in SKILLS_TS


def test_c5_hardmax_examples_featured_cover():
    entries = _entries()
    for sid in PHASE2_C:
        e = entries[sid]
        head = e.split("inputs:", 1)[0]
        assert f"cover: cover636('{sid}')" in head, sid
        assert "placeholder" not in e.lower(), sid
        assert "lovart" not in e.lower(), sid
        n = HARD_MAX[sid]
        ids = ", ".join(str(i) for i in range(1, n + 1))
        assert f"examples: ex636('{sid}', [{ids}])" in e, (sid, e[e.find("examples:"):e.find("examples:")+120])
        assert "video:" not in head, sid
        feat_n = FEAT_MIN[sid]
        fids = ", ".join(str(i) for i in range(1, feat_n + 1))
        assert f"featured: feat636('{sid}', [{fids}])" in e, sid


def test_no_gray_empty_examples_on_c():
    for sid in PHASE2_C:
        e = _entries()[sid]
        assert "examples: []" not in e and "featured: []" not in e, sid
