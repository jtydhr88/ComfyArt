"""#575 residual + #623: Explore scale/scrim intact; new6 hover video wired @ WASH_623_NEW6_VIDEO; motion×2 still waits (#622)."""
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
    # #623 new6 hover wired — pending list empty; pin + helper present (mutation surface)
    assert "WASH_623_NEW6_VIDEO" in SKILLS
    assert "d03ea7938877d084c201a94ef51f943dd0e061b9" in SKILLS
    assert "video594" in SKILLS and "594/wash/videos/" in SKILLS
    block = SKILL_VIDEO_PENDING_BLOCK()
    assert "SKILL_VIDEO_PENDING_NEW6 = [] as const" in block or "SKILL_VIDEO_PENDING_NEW6 = []" in block
    for sid in (
        "multi-angle",
        "logo-material",
        "meta-ads",
        "mobile-ui",
        "web-product",
        "marketing-campaign",
    ):
        assert f"video: video594('{sid}')" in SKILLS, sid
        assert sid not in block.split("=", 1)[-1].split("as const")[0] or "[]" in block


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


def test_residual_explore_scale_and_flat_scrim():
    """Design gold: Explore scale(1.05) @ 300ms; flat rgba(0,0,0,.3) scrim @ 150ms. No invent translateY/gradient."""
    assert "translateY(-2px)" not in CSS
    assert "linear-gradient(to top, rgba(0,0,0,.28)" not in CSS
    assert ".ca-skillcard__cover::after" not in CSS
    # Explore flat scrim kept
    assert ".ca-swall__cover::after" in CSS
    assert "background: rgba(0,0,0,.3)" in CSS
    assert "transition: opacity .15s" in CSS
    # Explore scale on stills + video
    assert ".ca-swall__card:hover .ca-swall__cover img" in CSS
    assert "transform: scale(1.05)" in CSS
    assert "transition: transform 300ms ease" in CSS
    # Home #605 scale left intact (no residual invent)
    assert ".ca-skillcard:hover .ca-skillcard__cover img" in CSS
    assert CSS.count("transform: scale(1.05)") >= 3  # home img, home video, explore img/video block


def test_forbid_ken_burns_fake_video():
    """No continuous pan/zoom fake-video on skill covers — stills use scale + flat scrim only."""
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
    return chr(10).join(out)


def test_mutation_new6_video_pin_must_stay():
    """Must-red mutation: drop WASH_623 pin / video594 / any new6 video: → red."""
    assert "WASH_623_NEW6_VIDEO" in SKILLS
    assert "d03ea7938877d084c201a94ef51f943dd0e061b9" in SKILLS
    for sid in (
        "multi-angle",
        "logo-material",
        "meta-ads",
        "mobile-ui",
        "web-product",
        "marketing-campaign",
    ):
        assert f"video: video594('{sid}')" in SKILLS, sid
