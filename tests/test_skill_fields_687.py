"""#687 unit — each Phase1 card's dialog field structure == the hard-coded Lovart spec (tests/lovart_fields_687.py).
Runs src/skills.ts through tests/js/fields_687.ts; $0, no network. Skips without node_modules (gate) — the e2e covers it there."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.lovart_fields_687 import MOTION_FEATURED_REMOVED, NOTE_PH_ZH, REF12, SPEC

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(
    not shutil.which("node") or not (ROOT / "node_modules/.bin/rolldown").exists(), reason="needs node + rolldown")


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("f687") / "fields_687.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "fields_687.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def rows(fields: list[dict]) -> list[tuple]:
    return [(f["key"], f["type"], f["required"], f["accept"], f["maxLength"], f["zh"], f["en"], f["phEn"]) for f in fields]


@needs_node
@pytest.mark.parametrize("sid", sorted(SPEC))
def test_dialog_fields_match_lovart_spec_687(got, sid):
    assert rows(got[sid]["fields"]) == SPEC[sid], sid


@needs_node
def test_motion_remake_template_and_featured03_removed_687(got):
    m = got["motion"]
    assert m["templates"] == 0 and m["presets"] == 0  # #687 decision: off-topic poster/first-last templates removed, none generated
    assert not any(MOTION_FEATURED_REMOVED in u for u in m["featured"]) and len(m["featured"]) == 3


@needs_node
def test_ref12_zh_placeholder_exact_687(got):
    assert len(REF12) == 12
    for sid in REF12:
        assert got[sid]["fields"][1]["phZh"] == NOTE_PH_ZH, sid


def test_typo_uploaded_file_are_uploaded_fixed_687():
    """No skill copy (src/skills.ts + every locale skills.* string) may contain the substring 'uploaded file'."""
    import json
    assert "uploaded file" not in (ROOT / "src/skills.ts").read_text().lower()
    for f in (ROOT / "src/locales").glob("*.json"):
        assert "uploaded file" not in json.dumps(json.loads(f.read_text()).get("skills", {}), ensure_ascii=False).lower(), f.name

def test_motion_title_desc_remake_687():
    import json
    from tests.lovart_fields_687 import MOTION_DESC_EN, MOTION_TITLE
    for lang in ("zh", "en"):
        loc = json.loads((ROOT / f"src/locales/{lang}.json").read_text())
        assert loc["skills.motionPoster"] == MOTION_TITLE[lang], lang
        assert "lock a still" not in loc["skills.desc.motion"] and "海报" not in loc["skills.desc.motion"]
    assert json.loads((ROOT / "src/locales/en.json").read_text())["skills.desc.motion"] == MOTION_DESC_EN
