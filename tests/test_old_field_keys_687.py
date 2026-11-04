"""#687 unit — by decision there is NO old→new field-key mapping. Old drafts / handoff values keyed by pre-#687 names
(brandInfo, stillArt, …) must not throw, must be ignored (dialog opens with empty new-key fields) and never reach the run."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.lovart_fields_687 import OLD_KEYS_687, SPEC

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(
    not shutil.which("node") or not (ROOT / "node_modules/.bin/rolldown").exists(), reason="needs node + rolldown")


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("o687") / "old_keys_687.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "old_keys_687.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True,
                                     env={**os.environ, "OLD": json.dumps(OLD_KEYS_687)}).stdout)


@needs_node
@pytest.mark.parametrize("sid", sorted(OLD_KEYS_687))
def test_old_keys_ignored_no_throw_687(got, sid):
    g = got[sid]
    assert g["error"] is None, (sid, g["error"])
    assert g["defaults"] == {row[0]: "" for row in SPEC[sid]}, sid  # dialog opens with the new keys, all empty
    assert not set(OLD_KEYS_687[sid]) & set(g["defaults"]), sid  # no old key survives as a field
    p = g["params"]
    assert p["ask"] == g["name"] and "ref" not in p, (sid, p)  # old values are dropped, not mapped
    assert all(k not in p for k in OLD_KEYS_687[sid]), sid
