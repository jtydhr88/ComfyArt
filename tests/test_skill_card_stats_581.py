"""#581: skill card footer + modal meta/share — real usage only; no fake favorite counts."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
SKILLS = (ROOT / "src/home/Skills.tsx").read_text()
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
HOME = (ROOT / "src/home/Home.tsx").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())

needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m581") / "skill_card_stats_581.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "skill_card_stats_581.ts"},
    )
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


def test_usage_store_api_exists():
    for name in ("loadSkillUsage", "recordSkillUse", "getSkillUsage", "skillShareUrl", "skillMetaLabel"):
        assert f"export function {name}" in SKILLS_TS
    assert "comfyart.skillUsage" in SKILLS_TS


def test_no_seed_or_fake_favorite_count():
    assert "Math.random" not in SKILLS_TS
    assert "skills-card-fav-count" not in SKILLS
    assert "favouriteCount" not in SKILLS + DLG + SKILLS_TS
    assert "Icons.heart" not in SKILLS  # membership toggle uses bookmark; no heart count
    assert "Lovart" not in SKILLS + DLG + SKILLS_TS


def test_card_usage_wiring():
    assert "skills-card-usage" in SKILLS
    assert "usage={usageMap[s.id] ?? 0}" in SKILLS
    assert "recordSkillUse" in SKILLS and "startDirect" in SKILLS
    assert "recordSkillUse" in HOME
    assert ".ca-swall__stat" in CSS


def test_modal_share_fav_meta_wiring():
    assert "skill-run-share" in DLG and "skillShareUrl" in DLG and "copyText" in DLG
    assert "skill-run-favourite" in DLG and "toggleFavourite" in DLG
    assert "skillMetaLabel(meta)" in DLG
    assert "recordSkillUse(skill.id)" in DLG
    assert ".ca-skillrun__actions" in CSS and ".ca-skillrun__iconbtn" in CSS


def test_i18n_keys():
    assert ZH["home.skillsUsage"] == "已使用 {0} 次"
    assert EN["home.skillsUsage"] == "Used {0} times"
    assert ZH["skillRun.usageAndTemplates"] == "已使用 {0} 次 · {1} 个模板"
    assert EN["skillRun.usageAndTemplates"] == "Used {0} times · {1} templates"
    assert ZH["skillRun.share"] == "分享" and EN["skillRun.share"] == "Share"
    assert ZH["skillRun.templateCount"] == "{0} 个模板"


@needs_node
def test_usage_empty_then_record(got):
    assert got["emptyUsage"] == {}
    assert got["productUses"] == 2 and got["posterUses"] == 1
    assert got["after"] == {"product-tvc-advertisement-generator": 2, "poster-differentiated-compiler": 1}
    # product has 6 templates; before record, usage 0 still returns templates-only meta
    assert got["metaProductBefore"] == {"templates": 7, "usage": 0}
    assert got["metaProductAfter"] == {"templates": 7, "usage": 2}
    # poster: no presets → usage-only meta after record
    assert got["metaPosterAfter"] == {"templates": 0, "usage": 1}
    assert got["metaEmptySkill"] is None


@needs_node
def test_meta_labels_and_share(got):
    assert got["zhJoined"] == "已使用 2 次 · 7 个模板"
    assert got["zhUsageOnly"] == "已使用 1 次"
    assert got["zhTemplatesOnly"] == "6 个模板"
    assert got["enJoined"] == "Used 2 times · 7 templates"
    assert got["share"] == "https://app.example/comfyart/?skill=product-tvc-advertisement-generator"
    assert "skill=poster" in got["sharePlain"] and got["sharePlain"].startswith("https://")
    assert got["share"]  # non-empty
    assert got["tShareZh"] == "分享"


@needs_node
def test_favourite_is_membership_not_count(got):
    assert got["favs"] == ["product-tvc-advertisement-generator"]
    # no numeric favorite source anywhere in card/dialog markup strings
    assert "skills-card-fav-count" not in SKILLS
    assert "favouriteCount" not in DLG
