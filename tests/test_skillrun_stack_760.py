"""#760 — rest = static multi-image pile (real media); card ≈258×193; hover/selected expand 400ms."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src/styles/home.css").read_text()
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
RAW = (ROOT / "src/skillRaw748.ts").read_text()


def test_400ms_expand_collapse_kept():
    assert "--ca-skillrun-stack-dur: 400ms" in CSS
    assert "--ca-skillrun-stack-ease: cubic-bezier(.25, .1, .25, 1)" in CSS
    assert "var(--ca-skillrun-stack-dur)" in CSS


def test_card_well_stays_160_120():
    assert "aspect-ratio: 160 / 120" in CSS and "width: 258px" not in CSS


def test_rest_is_static_pile_focus_expands():
    seg = CSS.split("#760 — product DOM")[1].split("「选择」")[0]
    assert "inset: var(--ca-skillrun-stack-inset)" in seg and "--ca-skillrun-stack-inset: 8px" in seg
    assert "height: 76.03%" in seg and "translateY(15.75%) scale(.757178)" in seg
    assert "nth-child(1) { --r: 5deg; }" in seg and "nth-child(2) { --r: -5deg; }" in seg and "nth-child(3) { --r: 10deg; }" in seg
    assert "nth-child(4)" not in seg and "z-index: calc(3 - var(--i))" in seg
    assert "--ca-skillrun-stack-cell: 32.11%" in seg and "--ca-skillrun-stack-pitch: 33.94%" in seg
    for stale in ("33px", "120px", "126", "252", "56%"):
        assert stale not in seg, stale
    assert "[data-on] .ca-skillrun__stack > *" in seg and ":hover .ca-skillrun__stack > *" in seg
    assert "stack.slice(0, 3)" in DLG


def test_stack_never_padded_with_pending():
    assert "j === 0 ? image : PENDING_WASH" not in RAW
    assert "stack.length > 1" in DLG
    seg = DLG[DLG.index('data-testid="skill-run-stack"'):][:400]
    assert "PendingWash" not in seg and "pending-wash" not in seg

def test_stack_pads_with_real_dup_never_pending():
    """depth>1 + ≥1 real → pad to min(depth,3) by duplicating last real; never PENDING_WASH."""
    assert "Never PENDING_WASH fillers" in RAW
    assert "while (stack.length < target) stack.push(stack[stack.length - 1]" in RAW
    assert "j === 0 ? image : PENDING_WASH" not in RAW
    assert "target > 1 && real.length > 0" in RAW


def test_skills_category_chip_200ms_not_select_pill():
    """Category chips For you / E-commerce / … = 200ms; card 「选择」/zoom stay 100ms."""
    chip = CSS.split(".ca-skills__chip {", 1)[1].split("}", 1)[0]
    assert "200ms" in chip
    assert "--ca-skillrun-hover-dur: 100ms" in CSS
    assert "--ca-skillrun-hover-dur: 200ms" not in CSS
    # #760 override (after the legacy 150ms rule) must drive pick/zoom via the 100ms token
    assert CSS.count(".ca-skillrun__zoom, .ca-skillrun__pick {") >= 2
    override = CSS.rsplit(".ca-skillrun__zoom, .ca-skillrun__pick {", 1)[1].split("}", 1)[0]
    assert "var(--ca-skillrun-hover-dur)" in override


def test_presetimg_contain_is_direct_child_only():
    """Cover/video contain must not override stack layer object-fit via descendant selector."""
    assert ".ca-skillrun__presetimg > img" in CSS
    # bare `.ca-skillrun__presetimg img` (no >) would steal stack cover
    import re
    bare = re.findall(r"\.ca-skillrun__presetimg\s+img\b", CSS)
    assert not bare, bare

def test_rest_pile_transform_origin_center():
    seg = CSS.split("#760 — product DOM")[1].split("「选择」")[0]
    assert "transform-origin: center center" in seg
    assert "scale(.757178)" in seg

