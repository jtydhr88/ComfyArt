"""#712 audit: every model id a built-in skill / template / auto-pick path / curated default can route to without the
user naming one is registered in the runtime catalog (api/wavespeed.py load_config), so no live skill hits the
UnregisteredModel error. Explicit fallbacks on auto rows must be registered too."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ComfyArt.api import auto_models, wavespeed

ROOT = Path(__file__).resolve().parent.parent
ID = re.compile(r'''["']([a-z0-9][\w.-]*/[\w.-]+(?:/[\w.-]+)*)["']''')
VENDORS = ("wavespeed-ai/", "minimax/", "recraft-ai/", "google/", "openai/", "bytedance/", "alibaba/", "kwaivgi/",
           "black-forest-labs/", "ideogram-ai/", "midjourney/", "pruna-ai/", "bria/", "tripo3d/", "mirelo-ai/")


def _catalog() -> dict[str, set[str]]:
    return {f: {m["id"] for m in v["models"]} for f, v in wavespeed.load_config()["features"].items()}


def used_ids() -> dict[str, str]:
    """id -> where it is used (first source)."""
    cfg, out = wavespeed.load_config(), {}
    for f, spec in auto_models.load_table().items():
        rows = [(c["id"], c) for c in spec.get("categories", [])] + [(k, spec[k]) for k in ("masked", "multi_reference") if spec.get(k)]
        for rid, r in rows:
            fb = r.get("fallback") or []
            for m in [r["model"], *([fb] if isinstance(fb, str) else fb)]:
                out.setdefault(m, f"auto_models.json {f}/{rid}")
    for f, v in cfg["features"].items():
        if v.get("default"):
            out.setdefault(v["default"], f"curated default {f}")
    files = [*sorted((ROOT / "src").rglob("*.ts")), *sorted((ROOT / "src").rglob("*.tsx")), *sorted((ROOT / "api").rglob("*.py"))]
    for p in files:
        if "locales" in p.parts:
            continue
        for m in ID.findall(p.read_text(encoding="utf-8")):
            if m.startswith(VENDORS) and not m.endswith((".png", ".json", ".mp4", ".svg")):
                out.setdefault(m, str(p.relative_to(ROOT)))
    return out


def test_builtin_paths_use_only_registered_models():
    cat = _catalog()
    every = set().union(*cat.values())
    missing = {m: where for m, where in used_ids().items() if m not in every}
    assert not missing, f"unregistered model ids used by built-in paths: {missing}"


@pytest.mark.parametrize("feature", ["text_to_image", "image_edit"])
def test_auto_rows_registered_for_their_feature(feature):
    cat = _catalog()[feature]
    spec = auto_models.load_table()[feature]
    for r in [*spec.get("categories", []), *[spec[k] for k in ("masked", "multi_reference") if spec.get(k)]]:
        auto_models.registered(r, cat, feature)  # raises UnregisteredModel when not
