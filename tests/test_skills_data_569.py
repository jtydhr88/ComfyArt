"""#569 (product ruling 6550618343 on #494): effect skills lose presets, template skills get the reference's three
inputs and template counts, character/motion wired from review-assets manifest 881494ff (motion assets @bd043d4c); character from manifest f81ce12a (v3 @b63d44ea, 04/05 v3.1 @9024565c).
Runs src/skills.ts through tests/js/skills_data_569.ts; $0, no network."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"), reason="needs node + npm install")

EFFECT = ("poster", "social", "thumbnail", "banner", "interior")
TEMPLATE = {"brand": 6, "packaging": 5, "character": 8, "product": 6, "motion": 2}
ASSETS = "https://raw.githubusercontent.com/ganjmeng/ComfyArt/bd043d4cff5019fc4117b5b2f3a33ae437015a28/569/wash"
CHARACTER = [("角色转身板", "Character Turnaround Sheet", "01-character-turnaround-sheet"),
             ("表情动作板", "Expression & Pose Sheet", "02-expression-pose-sheet"),
             ("建模细节参考板", "Modeling Detail Reference Sheet", "03-modeling-detail-reference-sheet"),
             ("服装/形态变体板", "Outfit / Form Variation Sheet", "04-outfit-form-variation-sheet"),
             ("道具互动板", "Prop Interaction Sheet", "05-prop-interaction-sheet"),
             ("基础角色板", "Basic Character Sheet", "06-basic-character-sheet"),
             ("完整技术角色板", "Complete Technical Character Sheet", "07-complete-technical-character-sheet"),
             ("时装大片角色板", "Editorial Fashion Sheet", "08-luxury-editorial-character-sheet")]  # product-final name (#574)
PINNED = {}  # motion only; character follows manifest f81ce12a below
V31 = "https://raw.githubusercontent.com/ganjmeng/ComfyArt/9024565c9857c5cb79e3bce85e636f5f102ad181/569/wash/character/templates/v3.1"
V31_FILES = ("04-outfit-form-variation-sheet", "05-prop-interaction-sheet")  # re-washed 04/05
CHARACTER_V2 = "https://raw.githubusercontent.com/ganjmeng/ComfyArt/b63d44ea61085a77a1c990605c31ae552db36c71/569/wash/character/templates/v3"
MOTION = [("海报动画", "Poster Animation", "01-poster-animation"),
          ("首帧到末帧动画", "First-to-Last Frame Animation", "02-first-to-last-frame-animation")]
# (zh label, type, required) — 当前模板 is the dialog's own preset row, so each template skill has 3 data inputs.
INPUTS = {
    "brand": [("品牌资料", "text", True), ("品牌素材", "image", False), ("视觉呈现方式", "text", False)],
    "packaging": [("商品与包装资料", "text", True), ("商品与包装素材", "image", False), ("视觉呈现方式", "text", False)],
    "character": [("角色参考图片", "image", False), ("角色资料", "text", False), ("视觉呈现方式", "text", False)],
    "product": [("商品图片", "image", True), ("商品资料", "text", False), ("视觉呈现方式", "text", False)],
    "motion": [("静态原稿", "image", True), ("动态要求", "text", False), ("视觉呈现方式", "text", False)],
}


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
        assert [(x["zh"], x["type"], x["required"]) for x in f] == [("上传文件", "image", False), ("补充描述", "textarea", False)], sid
        assert f[1]["ph"]["zh"] == "有什么想补充的吗？" and f[1]["ph"]["en"], sid
        assert all(x["en"] for x in f), sid


@needs_node
def test_template_counts(got):
    for sid, n in TEMPLATE.items():
        s = got["skills"][sid]
        assert len(s["presets"]) == n, sid
        assert s["meta"] == {"templates": n, "usage": 0}, sid
        assert len({p["id"] for p in s["presets"]}) == n and all(p["prompt"] and p["en"] and p["image"] for p in s["presets"]), sid
    assert got["skills"]["custom-workflow"]["presets"] is None


@needs_node
def test_character_has_no_examples(got):
    assert got["skills"]["character"]["examples"] is None
    for sid in ("brand", "packaging", "product", "motion"):
        assert not got["skills"][sid]["examples"], sid


@needs_node
def test_template_skills_three_inputs(got):
    for sid, want in INPUTS.items():
        f = got["skills"][sid]["inputs"]
        assert len(f) == 3, sid
        assert [(x["zh"], x["type"], x["required"]) for x in f] == want, sid
        assert all(x["en"] for x in f), sid
        assert all(x["ph"] and x["ph"]["zh"] and x["ph"]["en"] for x in f if x["type"] != "image"), sid
        assert f[-1]["key"] == "visual", sid


@needs_node
def test_character_and_motion_wired_from_manifest(got):
    for sid, rows in (("character", CHARACTER), ("motion", MOTION)):
        ps = got["skills"][sid]["presets"]
        assert [(p["zh"], p["en"]) for p in ps] == [(z, e) for z, e, _ in rows], sid
        assert [p["image"] for p in ps] == [(f"{V31 if f in V31_FILES else CHARACTER_V2}/{f}@thumb.webp" if sid == "character" else f"{ASSETS}/{sid}/templates/{f}@thumb.webp" if f not in PINNED else
                                             f"https://raw.githubusercontent.com/ganjmeng/ComfyArt/{PINNED[f]}/569/wash/{sid}/templates/{f}@thumb.webp")
                                            for _, _, f in rows], sid


@needs_node
def test_old_personal_skill_needs_no_migration(got):
    assert got["old"] == {"dialog": False, "meta": None}
