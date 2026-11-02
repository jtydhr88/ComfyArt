"""#601 soft FU: SkillRunDialog header≠CTA keys, filmstrip 01…10, Share+Bookmark wired (#581)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
EXAMPLES = (ROOT / "src/ui/SkillExamples.tsx").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())
SKILLS_TS = (ROOT / "src/skills.ts").read_text()

needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m601") / "skill_dialog_soft_601.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "skill_dialog_soft_601.ts"},
    )
    text = subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout.strip()
    return {"labels": text}


def test_header_and_cta_locale_keys_distinct():
    assert "skillRun.header" in ZH and "skillRun.header" in EN
    assert "skillRun.start" in ZH and "skillRun.start" in EN
    assert ZH["skillRun.header"] == "开始创作"
    assert EN["skillRun.header"] == "Start Creating"
    assert ZH["skillRun.start"] == "开始制作"
    assert EN["skillRun.start"] == "Start making"
    assert ZH["skillRun.header"] != ZH["skillRun.start"]
    assert EN["skillRun.header"] != EN["skillRun.start"]
    assert "skill-run-header" in DLG and "t('skillRun.header')" in DLG
    assert "skill-run-go" in DLG and "t('skillRun.start')" in DLG
    for blob in (DLG, EXAMPLES, SKILLS_TS, json.dumps(ZH), json.dumps(EN)):
        assert "Lovart" not in blob and "lovart" not in blob


@needs_node
def test_filmstrip_index_zero_padded(got):
    assert "export function filmstripIndexLabel" in SKILLS_TS
    assert "padStart(2, '0')" in SKILLS_TS
    assert "filmstripIndexLabel(i + 1)" in EXAMPLES
    assert got["labels"] == "01,02,09,10,11"


def test_share_and_bookmark_affordances_wired():
    # #581 landed share via skillShareUrl/copyText + local favourite toggle; #601 keeps them
    assert "skill-run-share" in DLG and "skillShareUrl" in DLG and "copyText" in DLG
    assert "skill-run-favourite" in DLG and "toggleFavourite" in DLG and "loadFavourites" in DLG
    assert "Icons.share" in DLG and "Icons.bookmark" in DLG
    assert ZH["skillRun.share"] == "分享" and EN["skillRun.share"] == "Share"
