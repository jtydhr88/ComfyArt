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


def test_card_size_matches_lovart_working():
    """Design @1280: Lovart left template card ≈258×193 (4:3)."""
    assert "width: 258px" in CSS
    assert "aspect-ratio: 4 / 3" in CSS
    assert "aspect-ratio: 160 / 120" not in CSS


def test_rest_is_static_pile_focus_expands():
    assert "--ca-skillrun-stack-w: 76%; --ca-skillrun-stack-h: 80%" in CSS
    assert "rotate(var(--r" in CSS
    assert ".ca-skillrun__stack > *:nth-child(1)" in CSS
    # hover OR selected expands
    assert "[data-on] .ca-skillrun__stack > *" in CSS
    assert ":hover .ca-skillrun__stack > *" in CSS


def test_stack_never_padded_with_pending():
    assert "j === 0 ? image : PENDING_WASH" not in RAW
    assert "stack.length > 1" in DLG
    seg = DLG[DLG.index('data-testid="skill-run-stack"'):][:400]
    assert "PendingWash" not in seg and "pending-wash" not in seg
