"""#636 Phase2-S3: B .ai NEW5 (merged + #637 wash) + C deferred.art5 production.
D style4 follow-up (may be cut). $0 static reads; no network. PRODUCT-LOCK-PHASE2 §B§C."""
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
PHASE2_C = [
    "naive-illustration",
    "logo-abstract",
    "photo-split-poster",
    "ppt-visual",
    "promo-ecommerce",
]
B_CATEGORY = {
    "flash-cut-video": "ads",
    "style-transfer": "branding",
    "person-swap": "ecommerce",
    "commerce-strategist": "ecommerce",
    "lifestyle-scene": "ecommerce",
}
C_CATEGORY = {
    "naive-illustration": "social",
    "logo-abstract": "branding",
    "photo-split-poster": "ads",
    "ppt-visual": "website",
    "promo-ecommerce": "ecommerce",
}
B_PRESET_MIN = {
    "flash-cut-video": 3,
    "style-transfer": 3,
    "person-swap": 3,
    "commerce-strategist": 3,
    "lifestyle-scene": 3,
}
C_PRESET_MIN = {
    "naive-illustration": 2,  # line / object
    "logo-abstract": 2,  # circle / angular
    "photo-split-poster": 2,  # hard / soft
    "ppt-visual": 3,  # cover / section / compare
    "promo-ecommerce": 2,  # kv / badge
}
B_REQUIRED_INPUTS = {
    "flash-cut-video": ["screenshot"],
    "style-transfer": ["contentImage", "styleImage"],
    "person-swap": ["scenePose", "faceRef", "outfitRef"],
    "commerce-strategist": ["sellPoints"],
    "lifestyle-scene": ["productImage"],
}
C_REQUIRED_INPUTS = {
    # #636 product lock: C5 Examples-only right rail = NEARMISS_INPUTS (Upload Files + Additional Details); no required topic fields
    "naive-illustration": [],
    "logo-abstract": [],
    "photo-split-poster": [],
    "ppt-visual": [],
    "promo-ecommerce": [],
}
TITLE_KEY_B = {
    "flash-cut-video": "skills.flashCutVideo",
    "style-transfer": "skills.styleTransfer",
    "person-swap": "skills.personSwap",
    "commerce-strategist": "skills.commerceStrategist",
    "lifestyle-scene": "skills.lifestyleScene",
}
TITLE_KEY_C = {
    "naive-illustration": "skills.naiveIllustration",
    "logo-abstract": "skills.logoAbstract",
    "photo-split-poster": "skills.photoSplitPoster",
    "ppt-visual": "skills.pptVisual",
    "promo-ecommerce": "skills.promoEcommerce",
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


def _assert_production(sid: str, cat: str, preset_min: int, required: list[str], entries: dict[str, str]):
    e = entries[sid]
    assert f"category: '{cat}'" in e, sid
    # #636 C soft wash: cover + examples/featured filled (hardMax layouts)
    head = e.split("inputs:", 1)[0]
    assert "cover: cover673(" in head, sid
    assert "examples: []" not in e and "featured: []" not in e, sid
    assert "feat673(" in e or "ex673(" in e, sid
    assert "video:" not in head, sid  # C stills only
    instr = _instructions(e)
    assert r"\n1)" in instr and r"\n5)" in instr, sid
    assert "You are a production" in instr, sid
    assert "Template:" not in instr, sid
    low = instr.lower()
    assert "demo" not in low and "lovart" not in low, sid
    assert "placeholder" not in e.lower(), sid
    body = e.split("presets:", 1)[1].split("inputs:", 1)[0]
    n = body.count("P(")
    assert n >= preset_min, (sid, n)
    assert body.count("Style: ") >= preset_min, sid
    for key in required:
        assert f"I('{key}'" in e, (sid, key)
    assert "inputs:" in e
    # C5 Examples-only uses shared NEARMISS_INPUTS; others keep inline I(...)
    tail = e.split("inputs:", 1)[1]
    assert ("NEARMISS_INPUTS" in tail) or ("I(" in tail), sid


def test_b5_production_instructions_presets_inputs_dialog():
    entries = _entries()
    assert set(PHASE2_B) <= set(entries)
    for sid, cat in B_CATEGORY.items():
        e = entries[sid]
        assert f"category: '{cat}'" in e, sid
        # #637 soft wash: cover + examples/featured filled (hardMax layouts)
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


def test_c5_production_instructions_presets_inputs_dialog():
    entries = _entries()
    assert set(PHASE2_C) <= set(entries)
    for sid, cat in C_CATEGORY.items():
        _assert_production(sid, cat, C_PRESET_MIN[sid], C_REQUIRED_INPUTS[sid], entries)
    for sid in PHASE2_C:
        assert "inputs: NEARMISS_INPUTS" in entries[sid], sid
        assert "VISUAL" not in entries[sid].split("inputs:", 1)[1], sid


def test_b5_lock_specific_guards():
    e = _entries()
    flash = _instructions(e["flash-cut-video"]).lower()
    assert "screenshot" in flash and ("flash-cut" in flash or "flash cut" in flash)
    assert "ugc" in flash or "tvc" in flash
    st = _instructions(e["style-transfer"]).lower()
    assert "identity" in st and "content" in st and "style" in st
    ps = _instructions(e["person-swap"]).lower()
    assert "three" in ps or "triple" in ps
    assert "pose" in ps and "scene" in ps
    cs = _instructions(e["commerce-strategist"]).lower()
    assert "strategy" in cs and ("board" in cs or "confirm" in cs)
    ls = _instructions(e["lifestyle-scene"]).lower()
    assert "textless" in ls
    assert "P('illustration'" in e["style-transfer"] and "P('photo'" in e["style-transfer"] and "P('graphic'" in e["style-transfer"]
    assert "P('3c'" in e["commerce-strategist"] and "P('beauty'" in e["commerce-strategist"] and "P('food'" in e["commerce-strategist"]
    assert "P('clean'" in e["flash-cut-video"] and "P('neon'" in e["flash-cut-video"] and "P('soft'" in e["flash-cut-video"]


def test_c5_lock_specific_guards():
    e = _entries()
    naive = _instructions(e["naive-illustration"]).lower()
    assert "giant" in naive and ("tiny" in naive or "mini" in naive)
    assert "rednote-cover-maker" in naive or "cover" in naive  # mutual exclusion
    logo = _instructions(e["logo-abstract"]).lower()
    assert "geometric" in logo and ("mark" in logo or "single" in logo)
    assert "material" in logo or "vi" in logo  # distinct from logo-material / brand VI
    split = _instructions(e["photo-split-poster"]).lower()
    assert "split" in split and "photo" in split
    assert "abstract" in split or "geometric" in split
    ppt = _instructions(e["ppt-visual"]).lower()
    assert "deck" in ppt or "slide" in ppt or "ppt" in ppt
    assert "16:9" in ppt or "16:9" in _instructions(e["ppt-visual"])
    promo = _instructions(e["promo-ecommerce"]).lower()
    assert "promo" in promo or "sale" in promo or "kv" in promo
    assert "white" in promo or "listing" in promo  # ≠ product white-bg
    # preset anchors
    assert "P('line'" in e["naive-illustration"] and "P('object'" in e["naive-illustration"]
    assert "P('circle'" in e["logo-abstract"] and "P('angular'" in e["logo-abstract"]
    assert "P('hard'" in e["photo-split-poster"] and "P('soft'" in e["photo-split-poster"]
    assert "P('cover'" in e["ppt-visual"] and "P('section'" in e["ppt-visual"] and "P('compare'" in e["ppt-visual"]
    assert "P('kv'" in e["promo-ecommerce"] and "P('badge'" in e["promo-ecommerce"]
    # website chip lit by ppt-visual
    assert "category: 'website'" in e["ppt-visual"]


def test_b5_locales_and_website_chip_untouched():
    for sid, key in TITLE_KEY_B.items():
        assert ZH[key].strip() and EN[key].strip()
        assert ZH[f"skills.desc.{sid}"] and EN[f"skills.desc.{sid}"]
        assert ZH[f"skills.cat.{sid}"] and EN[f"skills.cat.{sid}"]
    assert "category: 'website'" in SKILLS_TS
    assert "id: 'ppt-visual'" in SKILLS_TS
    assert "id: 'mobile-app-visual-design'" in SKILLS_TS and "id: 'web-product-visual-design'" in SKILLS_TS


def test_c5_locales():
    for sid, key in TITLE_KEY_C.items():
        assert ZH[key].strip() and EN[key].strip()
        assert ZH[f"skills.desc.{sid}"] and EN[f"skills.desc.{sid}"]
        assert ZH[f"skills.cat.{sid}"] and EN[f"skills.cat.{sid}"]


def test_dialog_path_and_no_lovart_no_fashion_ugc():
    assert 'data-testid="skill-run-go"' in DLG
    assert "hasSkillDialog" in SKILLS_TS
    assert "id: 'fashion-ugc'" not in SKILLS_TS and 'id: "fashion-ugc"' not in SKILLS_TS
    assert "Lovart" not in SKILLS_TS and "lovart" not in SKILLS_TS
    assert "#636" in SKILLS_TS


def test_ecommerce_phase2_ids_still_present_for_chips():
    for sid in ("person-swap", "commerce-strategist", "lifestyle-scene", "promo-ecommerce"):
        assert f"id: '{sid}'" in SKILLS_TS
        assert "category: 'ecommerce'" in _entries()[sid]


def test_d_style4_still_skeleton_not_touched():
    """C tip must not start D production fills."""
    e = _entries()
    for sid in ("yingzao", "crt-interface", "crayon-sketch", "fabric-collage"):
        instr = _instructions(e[sid])
        # D remains short skeleton voice (no "You are a production")
        assert "You are a production" not in instr, sid
