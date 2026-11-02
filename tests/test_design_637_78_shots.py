"""#637 #78 AFTER shoot entry (DESIGN_637_78_SHOOT=1)."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "docs/design/637/78/harness/shoot.py"

pytestmark = [
    pytest.mark.skipif(os.environ.get("DESIGN_637_78_SHOOT") != "1", reason="set DESIGN_637_78_SHOOT=1"),
    pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs dist"),
]


@pytest.mark.asyncio
async def test_637_78_after_shots(app_url):  # noqa: F811
    spec = importlib.util.spec_from_file_location("shoot637", MOD)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    await mod.capture(app_url)
    for sid in mod.SKILLS:
        for lang, theme in mod.COMBOS:
            p = mod.OUT / mod.shot_name(sid, lang, theme)
            assert p.is_file() and p.stat().st_size > 1000, p
