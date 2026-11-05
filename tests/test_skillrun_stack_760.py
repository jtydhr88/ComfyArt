"""#760 — rest = ONE cover <img> (contain+center), no CSS pile; click-expand keeps 400ms #751 timing, real media only."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src/styles/home.css").read_text()
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
RAW = (ROOT / "src/skillRaw748.ts").read_text()


def test_400ms_expand_collapse_kept():
    assert "--ca-skillrun-stack-dur: 400ms" in CSS
    assert "--ca-skillrun-stack-ease: cubic-bezier(.25, .1, .25, 1)" in CSS
    assert "transition: left var(--ca-skillrun-stack-dur) var(--ca-skillrun-stack-ease)" in CSS


def test_no_rest_pile_and_rotations():
    assert not re.search(r"\.ca-skillrun__stack > \*:nth-child", CSS)
    assert "rotate(var(--r" not in CSS
    assert ".ca-skillrun__preset[data-on] .ca-skillrun__stack { opacity: 1; }" in CSS
    assert "--ca-skillrun-stack-w: 76%; --ca-skillrun-stack-h: 80%" in CSS


def test_stack_never_padded_with_pending():
    assert "j === 0 ? image : PENDING_WASH" not in RAW
    assert "stack.length > 1" in DLG
    seg = DLG[DLG.index('data-testid="skill-run-stack"'):][:400]
    assert "PendingWash" not in seg and "pending-wash" not in seg
