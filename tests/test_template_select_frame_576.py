"""#576: skill template card selection ring wraps image only; title outside below."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "src/styles/home.css").read_text()
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()


def test_ring_on_image_not_whole_preset():
    assert ".ca-skillrun__preset[data-on] .ca-skillrun__presetimg::after" in CSS
    assert ".ca-skillrun__preset[data-on]::after" not in CSS
    # no whole-tile ring leftover
    assert ".ca-skillrun__preset::after" not in CSS


def test_title_sibling_below_framed_media():
    # title is sibling of presetimg inside the radio button (clickable), outside the framed media
    chunk = DLG[DLG.index('className="ca-skillrun__preset"'):DLG.index('ca-skillrun__presetname')]
    assert "ca-skillrun__presetimg" in chunk
    assert "ca-skillrun__presetname" not in chunk  # name opens after this slice
    # name appears after closing presetimg span
    assert DLG.index("ca-skillrun__presetimg") < DLG.index("ca-skillrun__presetname")


def test_title_gap_and_no_inset_padding():
    assert "gap: 8px" in CSS[CSS.index(".ca-skillrun__preset {"):CSS.index(".ca-skillrun__presetimg")]
    assert ".ca-skillrun__presetname { font: 400 13px/22px var(--ca-font); color: var(--ca-text-2); padding: 0; }" in CSS


def test_no_competitor_brand_in_src_change_paths():
    for rel in ("src/styles/home.css", "src/ui/SkillRunDialog.tsx"):
        body = (ROOT / rel).read_text().lower()
        assert "lovart" not in body
