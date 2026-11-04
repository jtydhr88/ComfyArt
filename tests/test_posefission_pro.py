"""#708: pose-fission runs on google/nano-banana-pro/edit at 2K, falls back to nano-banana-2.1/edit
only after a Pro failure (logged), and never silently swaps an unregistered pin. Template follows the
#708 FINAL plan-first spec. Mocks only: no WaveSpeed HTTP."""
import json
import logging
import pathlib
import re

import pytest

from ComfyArt.api import auto_models, wavespeed
from ComfyArt.api.mcp_tools import canvas

PRO = "google/nano-banana-pro/edit"
NANO = "google/nano-banana-2.1/edit"
ROOT = pathlib.Path(canvas.__file__).resolve().parents[2]
ARGS = {"prompt": "Change only: profile", "refs": ["shape:base"], "skill": "pose-fission"}


def test_registry_row_is_explicit():
    row = json.loads((ROOT / "api/auto_models.json").read_text(encoding="utf-8"))["skills"]["pose-fission"]
    assert row["model"] == PRO and row["resolution"] == "2k" and row["ratio"] == "3:4" and row["fallback"] == NANO
    assert "ultra" not in json.dumps(row)
    assert auto_models.skill_pin("pose-fission")["model"] == PRO
    assert auto_models.skill_pin("person-swap") is None and auto_models.skill_pin(None) is None


def test_pose_fission_picks_pro_2k():
    c = canvas._auto_choice("generate_image", dict(ARGS))
    assert c["model"] == c["edit_model"] == PRO and c["category"] == "skill" and c["resolution"] == "2k"
    a = canvas._pin_args(dict(ARGS), c)
    assert a["edit_model"] == PRO and a["edit_resolution"] == "2k" and a["ratio"] == "3:4"


def test_other_calls_unchanged():
    assert canvas._auto_choice("generate_image", {"prompt": "x", "refs": ["shape:a"]})["model"] != PRO
    # a user-named model still wins over the pin
    assert canvas._auto_choice("generate_image", {**ARGS, "model": NANO})["category"] != "skill"


def test_fallback_only_after_pro_failure_and_logged(caplog):
    with caplog.at_level(logging.WARNING):
        c = canvas._fallback_choice("generate_image", dict(ARGS), PRO)
    assert c["model"] == c["edit_model"] == NANO and c["fallback"] == PRO and c["category"] == "skill_fallback"
    assert any("falling back to " + NANO in r.getMessage() for r in caplog.records)
    assert canvas._fallback_choice("generate_image", dict(ARGS), NANO) is None


def test_unregistered_pin_never_silently_falls_back(monkeypatch, caplog):
    real = canvas.load_config()
    cfg = json.loads(json.dumps(real))
    cfg["features"]["image_edit"]["models"] = [m for m in cfg["features"]["image_edit"]["models"] if m["id"] != PRO]
    monkeypatch.setattr(canvas, "load_config", lambda: cfg)
    with caplog.at_level(logging.ERROR):
        c = canvas._auto_choice("generate_image", dict(ARGS))
    assert c["category"] == "skill_unregistered" and "edit_model" not in c
    assert canvas._unregistered_block(c)["status"] == "failed"
    assert any("not in the catalog" in r.getMessage() for r in caplog.records)


def test_schema_accepts_skill():
    assert canvas.SPECS["generate_image"]["inputSchema"]["properties"]["skill"] == {"type": "string"}


def test_payload_honours_explicit_resolution():
    schema = {"properties": {"resolution": {"enum": ["1k", "2k", "4k"]}, "aspect_ratio": {"enum": ["1:1", "3:4", "4:3"]}}}
    # 3:4 at 2K short side guesses 4k from the long side; the pin keeps 2k
    assert wavespeed._resolution(["1k", "2k", "4k"], 2731) == "4k"
    assert "inputs.get(\"resolution\")" in pathlib.Path(wavespeed.__file__).read_text()


def _template():
    src = (ROOT / "src/skills.ts").read_text(encoding="utf-8")
    m = re.search(r"\{ id: 'pose-fission'.*?instructions: '(.*?)',\n", src, re.S)
    return m.group(1)


@pytest.mark.parametrize("needle", [
    "Plan first, then confirm", "是否生成这 4 张", "A 开始生成", "B 换一组", "C 其他",
    "画面下边缘切在腰线/肚脐处", "正侧面 90°，看不到对侧眼睛", "头转向肩后 90°，下巴越过肩线",
    "保留金标的硬光方向和斑驳投影，落在脸部和衣服上", "change ONLY camera angle and framing", "Same person, same identity",
    "same outfit", "same light direction", "3:4", "never a grid", "no repeats", "at most 1 frontal 0°",
    "head and body at 0°", "head turned 45° from camera", "strict 90° side profile", "head turned 90° back over the shoulder",
    "body and head at 180°", "bottom edge of the frame cuts exactly at the navel", "bottom edge of the frame cuts at the collarbones",
    "dappled light and cast shadows fall across the face and the clothing", "No flat lighting, no white backdrop, no heavy filter or skin smoothing",
    "≤ planned + 2", "exactly the planned number",
    'skill: "pose-fission"', "one generate_image call per plan line",
])
def test_template_fields(needle):
    assert needle in _template()


def test_template_no_bare_half_body_label_and_no_ultra():
    t = _template()
    assert "ultra" not in t.lower()
    assert "(no full body / waist-up / half body / close-up / 半身)" in t  # only as the banned list


def test_navel_cut_is_hard_frame_edge():
    t = _template()
    assert "画面下边缘切在肚脐处，肚脐以下不入画，人物头顶到肚脐占满画面高度" in t
    assert "nothing below the navel is in frame" in t and "from top of head to navel fills the full frame height" in t
