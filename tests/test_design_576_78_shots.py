"""#576 #78 AFTER tip-pin screenshots. Opt-in: DESIGN_576_78_SHOOT=1"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
SHOT_MOD = ROOT / "docs/design/576/78/harness/shoot.py"
pytestmark = [
    pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/"),
    pytest.mark.skipif(os.environ.get("DESIGN_576_78_SHOOT") != "1", reason="set DESIGN_576_78_SHOOT=1 to re-shoot"),
]


def _load():
    spec = importlib.util.spec_from_file_location("design_576_78_shoot", SHOT_MOD)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.asyncio
async def test_576_78_after_shots(app_url):  # noqa: F811
    mod = _load()
    await mod.capture(app_url)
    out = ROOT / "docs/design/576/78/left-ours"
    for name in mod.SHOTS:
        p = out / name
        assert p.is_file() and p.stat().st_size > 800, p
