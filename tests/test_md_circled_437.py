import pytest
"""#437: .ca-md ships a unicode-range face for U+2460–U+2473 so ①②③… match 13px/1.6 body."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src/styles/overlays.css").read_text()
FONT = ROOT / "src/fonts/ca-enclosed.woff2"


def test_enclosed_font_face_and_asset_437():
    assert '@font-face' in CSS and 'CA Enclosed' in CSS
    assert 'unicode-range: U+2460-2473' in CSS
    assert 'ca-enclosed.woff2' in CSS
    assert FONT.is_file() and FONT.stat().st_size > 1000
    # .ca-md uses the face ahead of --ca-font at 13px / 1.6 / 400
    assert 'font: 400 13px/1.6 "CA Enclosed", var(--ca-font)' in CSS


@pytest.mark.gate_skip(reason="needs fontTools, which the gate venv does not install (#437)")
def test_enclosed_woff2_covers_2460_2473_437():
    from fontTools.ttLib import TTFont
    cmap = TTFont(str(FONT)).getBestCmap()
    missing = [hex(cp) for cp in range(0x2460, 0x2474) if cp not in cmap]
    assert not missing, missing
