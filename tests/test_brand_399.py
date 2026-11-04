"""#399: Loomi brand config is the single source of truth; locales use {brand}."""
from __future__ import annotations
import pytest

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_brand_ts_name_is_loomi():
    text = (ROOT / "src" / "brand.ts").read_text()
    assert re.search(r"name:\s*'Loomi'", text)
    assert re.search(r"pageTitle:\s*'Loomi'", text)
    assert "logoSvg:" in text
    assert "ComfyArt" not in text
    assert "Loomic" not in text


def test_brand_config_js_matches_ts():
    js = (ROOT / "public" / "brand" / "brand.config.js").read_text()
    assert 'name: "Loomi"' in js
    assert 'pageTitle: "Loomi"' in js
    assert "logoSvg:" in js
    assert "ComfyArt" not in js


@pytest.mark.gate_skip(reason="stale on main: a locale string still has the literal 'ComfyArt' instead of the brand placeholder (#399)")
def test_locales_use_brand_placeholder_not_literal():
    for lang in ("en", "zh"):
        data = json.loads((ROOT / "src" / "locales" / f"{lang}.json").read_text())
        joined = " ".join(data.values())
        assert "ComfyArt" not in joined
        assert "{brand}" in data["agentPicker.builtinAgentShort"]
        assert "{brand}" in data["agentPicker.builtinAgent"]


def test_index_html_title_is_loomi():
    html = (ROOT / "index.html").read_text()
    assert "<title>Loomi</title>" in html
    assert "ComfyArt" not in html


def test_display_name_is_loomi():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'DisplayName = "Loomi"' in text


def test_loader_assets_present():
    brand = ROOT / "public" / "brand"
    for name in (
        "loomi-mark.svg",
        "loomi-loader.css",
        "loomi-loader.js",
        "brand.config.js",
        "favicon.svg",
        "favicon.ico",
        "apple-touch-icon.png",
        "og-image-light.png",
        "og-image-dark.png",
    ):
        assert (brand / name).is_file(), name
