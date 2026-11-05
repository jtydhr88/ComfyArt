"""#569 (product ruling 6550618343 on #494): effect skills lose presets, template skills get the reference's three
inputs and template counts, character/motion wired from review-assets manifest 881494ff (motion assets @bd043d4c); character from manifest f81ce12a (v3 @b63d44ea, 04/05 v3.1 @9024565c).
Runs src/skills.ts through tests/js/skills_data_569.ts; $0, no network."""
from __future__ import annotations

import json
from tests.lovart_fields_687 import RAW_748
from tests.skill_ids_748 import TEMPLATE_IDS
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")

EFFECT = ("poster-differentiated-compiler", "banner-design-director", "interior-architectural-visualization", "cover-design-director")  # #641: thumbnail dialog parity → no presets
TEMPLATE = {sid: len(RAW_748[sid]["templates"]) for sid in TEMPLATE_IDS}  # #748 Final: raw template counts (character 7+ext 1, product 7, motion 2)
ASSETS = "https://raw.githubusercontent.com/ganjmeng/ComfyArt/bd043d4cff5019fc4117b5b2f3a33ae437015a28/569/wash"
CHARACTER = [("角色转身板", "Character Turnaround Sheet", "01-character-turnaround-sheet"),
             ("表情动作板", "Expression & Pose Sheet", "02-expression-pose-sheet"),
             ("建模细节参考板", "Modeling Detail Reference Sheet", "03-modeling-detail-reference-sheet"),
             ("服装/形态变体板", "Outfit / Form Variation Sheet", "04-outfit-form-variation-sheet"),
             ("道具互动板", "Prop Interaction Sheet", "05-prop-interaction-sheet"),
             ("基础角色板", "Basic Character Sheet", "06-basic-character-sheet"),
             ("完整技术角色板", "Complete Technical Character Sheet", "07-complete-technical-character-sheet"),
             ("时装大片角色板", "Editorial Fashion Sheet", "08-luxury-editorial-character-sheet")]  # #748: raw 7 + own ext 1
PINNED = {}  # motion only; character follows manifest f81ce12a below
V31 = "https://raw.githubusercontent.com/ganjmeng/ComfyArt/9024565c9857c5cb79e3bce85e636f5f102ad181/569/wash/character/templates/v3.1"
V31_FILES = ("04-outfit-form-variation-sheet", "05-prop-interaction-sheet")  # re-washed 04/05
CHARACTER_V2 = "https://raw.githubusercontent.com/ganjmeng/ComfyArt/b63d44ea61085a77a1c990605c31ae552db36c71/569/wash/character/templates/v3"
MOTION = [("海报动画", "Poster Animation", "01-poster-animation"),
          ("首帧到末帧动画", "First-to-Last Frame Animation", "02-first-to-last-frame-animation")]
# (zh label, type, required) — 当前模板 is the dialog's own preset row, so each template skill has 3 data inputs.
# #687: brand / packaging / character → reference-card Upload + Additional; motion → Reference Video Remake
# (locked in tests/test_skill_fields_687.py). product keeps the #569 three fields.
INPUTS = {"product-tvc-advertisement-generator": [(q["label"]["zh"], q["type"] if q["type"] == "image" else ("textarea" if (q.get("maxLength") or 0) > 200 else "text"), q["required"])
                                                   for q in RAW_748["product-tvc-advertisement-generator"]["templates"][0]["inputs"]]}  # #748 Final raw


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m569") / "skills_data_569.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"], cwd=ROOT, check=True,
                   capture_output=True, env={**os.environ, "OUT": str(out), "ENTRY": "skills_data_569.ts"})
    return json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)


@needs_node
def test_effect_skills_have_no_presets(got):
    for sid in EFFECT:
        s = got["skills"][sid]
        assert s["presets"] is None, sid
        assert s["meta"] is None, sid  # no 「N 个模板」 line
        assert s["examples"], sid  # 效果示例 keep their carousel


@needs_node
def test_effect_skills_only_upload_and_note(got):
    for sid in EFFECT:
        f = got["skills"][sid]["inputs"]
        assert [(x["zh"], x["type"], x["required"]) for x in f] == [("上传文件", "image", True), ("补充描述", "textarea", True)], sid  # #748 Final example form
        assert f[1]["ph"]["zh"] == "请填写补充描述"  # #748 measured: one zh placeholder on every example-class card and f[1]["ph"]["en"], sid  # #687
        assert all(x["en"] for x in f), sid


@needs_node
def test_social_fashion_ugc_presets_keep_examples(got):
    # #748 Final: rednote-cover-maker is an example card — no templates, left carousel = our washed examples
    s = got["skills"]["rednote-cover-maker"]
    assert s["examples"], "rednote-cover-maker"
    assert s["presets"] is None, "rednote-cover-maker"


@needs_node
def test_template_counts(got):

    for sid, n in TEMPLATE.items():
        s = got["skills"][sid]
        assert len(s["presets"] or []) == n, sid
        assert s["meta"] == ({"templates": n, "usage": 0} if n else None), sid  # #687 motion: no templates → no meta line
        assert len({p["id"] for p in s["presets"] or []}) == n and all(p["prompt"] and p["en"] and p["image"] for p in s["presets"] or []), sid
    assert "custom-workflow" not in got["skills"]


@needs_node
def test_character_has_no_examples(got):
    assert got["skills"]["character-sheet-design"]["examples"] is None
    for sid in ("brand-identity-director", "packaging-design-director", "product-tvc-advertisement-generator", "motion-poster-generator"):
        assert not got["skills"][sid]["examples"], sid


@needs_node
def test_template_skills_three_inputs(got):
    for sid, want in INPUTS.items():
        f = got["skills"][sid]["inputs"]
        assert len(f) == len(want), sid
        assert [(x["zh"], x["type"], x["required"]) for x in f] == want, sid
        assert all(x["en"] for x in f), sid
        assert all(x["ph"] and x["ph"]["zh"] and x["ph"]["en"] for x in f if x["type"] != "image"), sid
        assert f[-1]["key"] == "visual_direction", sid


@needs_node
def test_character_and_motion_wired_from_manifest(got):
    assert [p["zh"] for p in got["skills"]["motion-poster-generator"]["presets"]] == ["海报动效", "首尾帧动画"]  # #748 raw overrides #687 removal
    for sid, rows in (("character-sheet-design", CHARACTER),):
        ps = got["skills"][sid]["presets"]
        assert [(p["zh"], p["en"]) for p in ps] == [(z, e) for z, e, _ in rows], sid
        assert [p["image"] for p in ps] == [(f"{V31 if f in V31_FILES else CHARACTER_V2}/{f}@thumb.webp" if sid == "character-sheet-design" else f"{ASSETS}/{sid}/templates/{f}@thumb.webp" if f not in PINNED else
                                             f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{PINNED[f]}/569/wash/{sid}/templates/{f}@thumb.webp")
                                            for _, _, f in rows], sid


@needs_node
def test_old_personal_skill_needs_no_migration(got):
    assert got["old"] == {"dialog": False, "meta": None}
