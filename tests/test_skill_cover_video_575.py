"""#575 residual: cover focus mask/lift + hover video contract. Soft P1; motion×2 / new6 video wait design."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text()
EXAMPLES = (ROOT / "src/ui/SkillExamples.tsx").read_text()
WALL = (ROOT / "src/home/Skills.tsx").read_text()
HOME = (ROOT / "src/home/Home.tsx").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()


def test_no_lovart_in_src():
    src_root = ROOT / "src"
    hits = []
    for p in src_root.rglob("*"):
        if p.is_file() and p.suffix in {".ts", ".tsx", ".css", ".json"}:
            text = p.read_text(errors="ignore")
            if "Lovart" in text or "lovart" in text:
                hits.append(str(p.relative_to(ROOT)))
    assert hits == []


def test_video_helpers_and_pending_scaffold():
    assert "export function isSkillMediaVideo" in SKILLS
    assert "export function skillCoverVideoHover" in SKILLS
    assert "export function presetVideo" in SKILLS
    assert "SKILL_VIDEO_PENDING_NEW6" in SKILLS
    assert "TODO(design pin): motion" in SKILLS
    assert "569/wash/motion/templates" in SKILLS
    assert "bd043d4c" in SKILLS
    assert "video?: string" in SKILLS  # SkillPreset.video
    # new6 skills stay without video field until assets exist
    for sid in (
        "multi-angle",
        "logo-material",
        "meta-ads",
        "mobile-ui",
        "web-product",
        "marketing-campaign",
    ):
        assert sid in SKILL_VIDEO_PENDING_BLOCK()


def SKILL_VIDEO_PENDING_BLOCK() -> str:
    start = SKILLS.index("SKILL_VIDEO_PENDING_NEW6")
    return SKILLS[start : start + 400]


def test_explore_and_home_use_hover_helper():
    assert "skillCoverVideoHover" in WALL and "skillCoverVideoHover(videoRef.current, 'enter')" in WALL
    assert "skills-card-video" in WALL and "muted" in WALL and "loop" in WALL
    assert "skillCoverVideoHover" in HOME and "home-skill-card-video" in HOME
    assert "ca-skillcard__video" in CSS


def test_skill_examples_plays_mp4():
    assert "isSkillMediaVideo" in EXAMPLES
    assert "skill-run-example-stage-video" in EXAMPLES
    assert "muted" in EXAMPLES and "loop" in EXAMPLES and "playsInline" in EXAMPLES
    assert ".ca-skillrun__stage img, .ca-skillrun__stage video" in CSS


def test_residual_focus_mask_and_lift_css():
    """Focus/hover: scale + slight translateY lift + soft gradient mask on home + explore."""
    assert "scale(1.05) translateY(-2px)" in CSS
    assert ".ca-skillcard__cover::after" in CSS
    assert "linear-gradient(to top, rgba(0,0,0,.28)" in CSS
    assert ".ca-swall__cover::after" in CSS
    # no-video stills still animate (wall img transform rule present)
    assert ".ca-swall__card:hover .ca-swall__cover img" in CSS
    assert ".ca-skillcard:hover .ca-skillcard__cover img" in CSS


def test_forbid_ken_burns_fake_video():
    """No continuous pan/zoom fake-video on skill covers — stills use scale/mask only."""
    lower = CSS.lower()
    assert "kenburns" not in lower and "ken-burns" not in lower
    assert "no continuous pan/zoom fake-video" in CSS
    for needle in ("ca-skillcard__cover img", "ca-swall__cover img"):
        assert needle in CSS
    assert "ca-skillcard__cover" not in _keyframes_body(CSS)
    assert "ca-swall__cover" not in _keyframes_body(CSS)


def _keyframes_body(css: str) -> str:
    out = []
    i = 0
    while True:
        j = css.find("@keyframes", i)
        if j < 0:
            break
        k = css.find("{", j)
        depth = 0
        p = k
        while p < len(css):
            if css[p] == "{":
                depth += 1
            elif css[p] == "}":
                depth -= 1
                if depth == 0:
                    out.append(css[j : p + 1])
                    i = p + 1
                    break
            p += 1
        else:
            break
    return "\n".join(out)
