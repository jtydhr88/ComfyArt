"""#644 design HOLD (c): the skill dialog's 「N 个模板」 / 'N templates' label must equal the real thumbnail count the
dialog shows (Examples strip + preset tiles with media). taobao-product / before-after = 8, clothing-swap = 2.
Runs src/skills.ts through tests/js/thumb_count_644.ts; $0, no network."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(
    not shutil.which("node") or not (ROOT / "node_modules/.bin/rolldown").exists(), reason="needs node + rolldown")

EXPECTED = {"taobao-product": 8, "before-after": 8, "clothing-swap": 2}


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m644") / "thumb_count_644.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "thumb_count_644.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
@pytest.mark.parametrize("sid,n", sorted(EXPECTED.items()))
def test_skill_template_label_matches_thumbnails_644(got, sid, n):
    s = got[sid]
    assert s["thumbs"] == n and s["count"] == n and s["templates"] == n, (sid, s)


@needs_node
def test_skill_template_label_equals_thumbs_for_every_skill_644(got):
    bad = {k: v for k, v in got.items() if v["templates"] not in (0, v["thumbs"])}  # 0 = effect skill, no label
    assert not bad, bad
