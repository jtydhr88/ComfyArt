"""#637 Phase2-S4 B NEW5 soft wash — hardMax left-column layouts from phase2/bc-refs/*/meta.txt.
$0 static reads; no network. PRODUCT-LOCK-PHASE2 §B + product AC (person-swap max1, lifestyle max2)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()

WASH_637 = "2109c085aa74c617cd34517f99626f357062c81c"
PHASE2_B = [
    "flash-cut-video",
    "style-transfer",
    "person-swap",
    "commerce-strategist",
    "lifestyle-scene",
]
# hardMax examples count (Product AC locked)
HARD_MAX = {
    "flash-cut-video": 1,       # examples-single-video
    "style-transfer": 4,        # examples-carousel slots4
    "person-swap": 1,           # examples-single-still hard max1
    "commerce-strategist": 1,   # examples-single-video
    "lifestyle-scene": 2,       # examples-carousel hard max2
}
VIDEO_SKILLS = {"flash-cut-video", "commerce-strategist"}
FEAT_MIN = {
    "flash-cut-video": 5,
    "style-transfer": 5,
    "person-swap": 3,
    "commerce-strategist": 5,
    "lifestyle-scene": 3,
}


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a : next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def test_wash_637_pin_and_helpers():
    assert f"const WASH_637 = '{WASH_637}'" in SKILLS_TS
    for h in ("cover637", "ex637", "feat637", "video637"):
        assert f"const {h}" in SKILLS_TS or f"{h} =" in SKILLS_TS or f"{h}(" in SKILLS_TS


def test_b5_hardmax_examples_featured_cover_video():
    entries = _entries()
    for sid in PHASE2_B:
        e = entries[sid]
        head = e.split("inputs:", 1)[0]
        assert f"cover: cover637('{sid}')" in head, sid
        assert "placeholder" not in e.lower(), sid
        assert "lovart" not in e.lower(), sid
        n = HARD_MAX[sid]
        if sid in VIDEO_SKILLS:
            assert f"examples: [video637('{sid}')]" in e, sid
            assert f"video: video637('{sid}')" in head, sid
        else:
            ids = ", ".join(str(i) for i in range(1, n + 1))
            assert f"examples: ex637('{sid}', [{ids}])" in e, (sid, e[e.find("examples:"):e.find("examples:")+80])
            assert "video: video637" not in head, sid
        feat_n = FEAT_MIN[sid]
        ids = ", ".join(str(i) for i in range(1, feat_n + 1))
        assert f"featured: feat637('{sid}', [{ids}])" in e, sid


def test_no_gray_empty_examples_on_b():
    for sid in PHASE2_B:
        e = _entries()[sid]
        assert "examples: []" not in e and "featured: []" not in e, sid
