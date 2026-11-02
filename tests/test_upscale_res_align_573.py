"""#573: upscale panel resolution Pick — collapsed current value left-aligned like options."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "src/styles/overlays.css").read_text()
SRC = (ROOT / "src/ui/UpscaleMenu.tsx").read_text()


def test_toolpanel_res_pick_text_align_left():
    """Collapsed trigger uses text-align:left so button UA center does not misalign vs options."""
    block = CSS[CSS.index(".ca-toolpanel__res .ca-pick"):]
    rule = block[: block.index("}")]
    assert "text-align: left" in rule


def test_res_still_uses_pick_not_native_select():
    assert 'data-res-pick' in SRC
    assert "<Pick " in SRC
    assert "<select" not in SRC


def test_menu_items_keep_left_align():
    base = (ROOT / "src/styles/base.css").read_text()
    item = base[base.index(".ca-menu__item {"): base.index(".ca-menu__item:hover")]
    assert "text-align: left" in item


def test_no_competitor_brand_in_touched_src():
    for rel in ("src/styles/overlays.css", "src/ui/UpscaleMenu.tsx", "src/ui/StyleToolbars.tsx"):
        body = (ROOT / rel).read_text().lower()
        assert "lovart" not in body
