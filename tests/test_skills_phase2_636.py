"""#636 Phase2-S3 B-first: production instructions/inputs/presets for .ai NEW5.
C/D follow-up tips. $0 static reads; no network. PRODUCT-LOCK-PHASE2 §B."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_TS = (ROOT / "src/skills.ts").read_text()
DLG = (ROOT / "src/ui/SkillRunDialog.tsx").read_text()
ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())

PHASE2_B = [
    "flash-cut-video",
    "style-transfer",
    "person-swap",
    "commerce-strategist",
    "lifestyle-scene",
]
B_CATEGORY = {
    "flash-cut-video": "ads",
    "style-transfer": "branding",
    "person-swap": "ecommerce",
    "commerce-strategist": "ecommerce",
    "lifestyle-scene": "ecommerce",
}
B_PRESET_MIN = {
    "flash-cut-video": 3,  # clean / neon / soft
    "style-transfer": 3,  # illustration / photo / graphic
    "person-swap": 3,
    "commerce-strategist": 3,  # 3c / beauty / food
    "lifestyle-scene": 3,
}
B_REQUIRED_INPUTS = {
    "flash-cut-video": ["screenshot"],
    "style-transfer": ["contentImage", "styleImage"],
    "person-swap": ["scenePose", "faceRef", "outfitRef"],
    "commerce-strategist": ["sellPoints"],
    "lifestyle-scene": ["productImage"],
}
TITLE_KEY = {
    "flash-cut-video": "skills.flashCutVideo",
    "style-transfer": "skills.styleTransfer",
    "person-swap": "skills.personSwap",
    "commerce-strategist": "skills.commerceStrategist",
    "lifestyle-scene": "skills.lifestyleScene",
}


def _entries() -> dict[str, str]:
    a = SKILLS_TS.index("export const BUILTIN_SKILLS")
    block = SKILLS_TS[a : next(i for i in (SKILLS_TS.find("\n])\n", a), SKILLS_TS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def _instructions(entry: str) -> str:
    m = re.search(r"instructions: '((?:\\'|[^'])*)'", entry)
    assert m, entry[:120]
    return m.group(1)


def test_b5_production_instructions_presets_inputs_dialog():
    entries = _entries()
    assert set(PHASE2_B) <= set(entries)
    for sid, cat in B_CATEGORY.items():
        e = entries[sid]
        assert f"category: '{cat}'" in e, sid
        # #637 soft wash: cover + examples/featured filled (hardMax layouts); C tip still empty
        head = e.split("inputs:", 1)[0]
        assert "cover: cover637(" in head, sid
        assert "examples: []" not in e and "featured: []" not in e, sid
        assert "feat637(" in e or "ex637(" in e or "video637(" in e, sid
        instr = _instructions(e)
        assert r"\n1)" in instr and r"\n5)" in instr, sid
        assert "You are a production" in instr, sid
        assert "Template:" not in instr, sid
        low = instr.lower()
        assert "demo" not in low and "lovart" not in low, sid
        assert "placeholder" not in e.lower(), sid
        body = e.split("presets:", 1)[1].split("inputs:", 1)[0]
        n = body.count("P(")
        assert n >= B_PRESET_MIN[sid], (sid, n)
        assert body.count("Style: ") >= B_PRESET_MIN[sid], sid
        for key in B_REQUIRED_INPUTS[sid]:
            assert f"I('{key}'" in e, (sid, key)
        # dialog-capable
        assert "inputs:" in e and "I(" in e.split("inputs:", 1)[1]


def test_b5_lock_specific_guards():
    e = _entries()
    flash = _instructions(e["flash-cut-video"]).lower()
    assert "screenshot" in flash and ("flash-cut" in flash or "flash cut" in flash)
    assert "ugc" in flash or "tvc" in flash  # mutual exclusion vs motion
    st = _instructions(e["style-transfer"]).lower()
    assert "identity" in st and "content" in st and "style" in st
    ps = _instructions(e["person-swap"]).lower()
    assert "three" in ps or "triple" in ps
    assert "pose" in ps and "scene" in ps
    cs = _instructions(e["commerce-strategist"]).lower()
    assert "strategy" in cs and ("board" in cs or "confirm" in cs)
    ls = _instructions(e["lifestyle-scene"]).lower()
    assert "textless" in ls
    # preset id anchors from lock table
    assert "P('illustration'" in e["style-transfer"] and "P('photo'" in e["style-transfer"] and "P('graphic'" in e["style-transfer"]
    assert "P('3c'" in e["commerce-strategist"] and "P('beauty'" in e["commerce-strategist"] and "P('food'" in e["commerce-strategist"]
    assert "P('clean'" in e["flash-cut-video"] and "P('neon'" in e["flash-cut-video"] and "P('soft'" in e["flash-cut-video"]


def test_b5_locales_and_website_chip_untouched():
    for sid, key in TITLE_KEY.items():
        assert ZH[key].strip() and EN[key].strip()
        assert ZH[f"skills.desc.{sid}"] and EN[f"skills.desc.{sid}"]
        assert ZH[f"skills.cat.{sid}"] and EN[f"skills.cat.{sid}"]
    # ppt-visual website chip still lit (C skeleton remains; do not regress)
    assert "category: 'website'" in SKILLS_TS
    assert "id: 'ppt-visual'" in SKILLS_TS
    assert "id: 'mobile-ui'" in SKILLS_TS and "id: 'web-product'" in SKILLS_TS


def test_dialog_path_and_no_lovart_no_fashion_ugc():
    assert 'data-testid="skill-run-go"' in DLG
    assert "hasSkillDialog" in SKILLS_TS
    assert "id: 'fashion-ugc'" not in SKILLS_TS and 'id: "fashion-ugc"' not in SKILLS_TS
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
    assert "#636" in SKILLS_TS


def test_ecommerce_phase2_ids_still_present_for_chips():
    # #634 chip awareness — do not drop ecommerce NEW ids
    for sid in ("person-swap", "commerce-strategist", "lifestyle-scene", "promo-ecommerce"):
        assert f"id: '{sid}'" in SKILLS_TS
        assert "category: 'ecommerce'" in _entries()[sid]
